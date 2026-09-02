"""
db.py
Utilitários de persistência em PostgreSQL para o pipeline.
 - Conexão via SQLAlchemy (driver psycopg)
 - Criação de schema (DDL) idempotente
 - Criação de views para manter consistência com os CSVs previamente gerados
 - Helpers de upsert (dimensões) e inserção em lote (fatos)
"""

from __future__ import annotations

from typing import Iterable, Sequence

import math
import json
import pandas as pd
from sqlalchemy import create_engine, text, bindparam
from sqlalchemy.types import JSON

import config

_ENGINE = None


def get_engine():
    global _ENGINE
    if _ENGINE is None:
        url = (
            f"postgresql+psycopg://{config.PG_USER}:{config.PG_PASSWORD}"
            f"@{config.PG_HOST}:{config.PG_PORT}/{config.PG_DATABASE}"
        )
        _ENGINE = create_engine(url, pool_pre_ping=True, future=True)
    return _ENGINE


def _to_int_or_none(v):
    """Converte valores como '2', '2.0', 2.0 para int; vazio/NaN vira None."""
    if v is None:
        return None
    try:
        if isinstance(v, str):
            s = v.strip()
            if s == "" or s.lower() == "nan":
                return None
            return int(float(s))
        if isinstance(v, float):
            if math.isnan(v):
                return None
            return int(v)
        return int(v)
    except Exception:
        return None


def _to_float_or_none(v):
    if v is None:
        return None
    try:
        if isinstance(v, str):
            s = v.strip()
            if s == "" or s.lower() == "nan":
                return None
            return float(s)
        if isinstance(v, float):
            if math.isnan(v):
                return None
            return v
        return float(v)
    except Exception:
        return None


def _exec_batch(conn, sql, rows: Sequence, chunk: int = 5000):
    """Execute bateladas com SQLAlchemy 2.0.
    Aceita lista de dicts OU lista de sequências; no segundo caso,
    converte para dicts mapeando índices para nomes ':0', ':1', ...
    """
    if not rows:
        return
    total = len(rows)
    try:
        # aceita string ou TextClause/Executable
        from sqlalchemy.sql.elements import TextClause
        stmt = sql if isinstance(sql, TextClause) else text(sql)
    except Exception:
        stmt = text(sql)
    for i in range(0, total, chunk):
        part = rows[i : i + chunk]
        if part and not isinstance(part[0], dict):
            dicts = []
            for row in part:
                d = {str(j): v for j, v in enumerate(row)}
                dicts.append(d)
        else:
            dicts = part
        conn.execute(stmt, dicts)


def init_db():
    """Cria tabelas e views (idempotente)."""
    eng = get_engine()
    with eng.begin() as conn:
        # Tabelas de dimensão
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS dim_municipio (
                cod_municipio TEXT PRIMARY KEY,
                nome          TEXT,
                uf            TEXT
            );
            """
        ))

        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS dim_escola (
                cod_escola     TEXT PRIMARY KEY,
                nome           TEXT,
                cod_municipio  TEXT REFERENCES dim_municipio(cod_municipio)
            );
            """
        ))

        # Fatos (inclui colunas necessárias para views consistentes com os CSVs)
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS fact_censo_medida (
                ano             INT,
                uf              TEXT,
                cod_municipio   TEXT,
                nome_municipio  TEXT,
                tp_dependencia  TEXT,
                tp_localizacao  TEXT,
                cod_escola      TEXT,
                nome_escola     TEXT,
                grupo           TEXT,
                etapa           TEXT,
                qt              INT,
                CONSTRAINT pk_fact_censo_medida UNIQUE (ano, cod_escola, grupo, etapa)
            );
            """
        ))

        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS fact_infra_escola (
                ano               INT,
                uf                TEXT,
                cod_municipio     TEXT,
                nome_municipio    TEXT,
                tp_dependencia    TEXT,
                rede_tipo         TEXT,
                tp_localizacao    TEXT,
                localizacao_tipo  TEXT,
                cod_escola        TEXT,
                nome_escola       TEXT,
                grupo_infra       TEXT,
                item              TEXT,
                possui            INT,
                CONSTRAINT pk_fact_infra_escola UNIQUE (ano, cod_escola, item)
            );
            """
        ))

        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS fact_indigena (
                ano             INT,
                uf              TEXT,
                cod_municipio   TEXT,
                nome_municipio  TEXT,
                tp_dependencia  TEXT,
                tp_localizacao  TEXT,
                cod_escola      TEXT,
                nome_escola     TEXT,
                categoria       TEXT,
                grupo           TEXT,
                etapa           TEXT,
                qt              INT,
                CONSTRAINT pk_fact_indigena UNIQUE (ano, cod_escola, categoria, grupo, etapa)
            );
            """
        ))

        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS fact_tx_rendimento (
                ano                 INT,
                regiao              TEXT,
                uf                  TEXT,
                cod_municipio       TEXT,
                nome_municipio      TEXT,
                cod_escola          TEXT,
                nome_escola         TEXT,
                localizacao         TEXT,
                dependencia         TEXT,
                etapa               TEXT,
                serie               INT,
                metrica             TEXT,
                valor               TEXT,
                valor_num           DOUBLE PRECISION,
                valor_prop          DOUBLE PRECISION,
                CONSTRAINT pk_fact_tx_rendimento UNIQUE (ano, uf, cod_municipio, cod_escola, etapa, serie, metrica)
            );
            """
        ))

        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS siope_registro_raw (
                id             BIGSERIAL PRIMARY KEY,
                num_ano        INT,
                num_peri       INT,
                sig_uf         TEXT,
                cod_muni       TEXT,
                periodo_label  TEXT,
                payload        JSONB
            );
            """
        ))

        # Views que refletem os CSVs anteriores (nomes/ordem de colunas)
        conn.execute(text(
            """
            CREATE OR REPLACE VIEW vw_dados_normalizados_por_etapa AS
            SELECT
                ano            AS "NU_ANO_CENSO",
                uf             AS "SG_UF",
                cod_municipio  AS "CO_MUNICIPIO",
                nome_municipio AS "NO_MUNICIPIO",
                tp_dependencia AS "TP_DEPENDENCIA",
                tp_localizacao AS "TP_LOCALIZACAO",
                cod_escola     AS "CO_ENTIDADE",
                nome_escola    AS "NO_ENTIDADE",
                grupo          AS "Grupo",
                etapa          AS "Etapa",
                qt             AS "QT"
            FROM fact_censo_medida;
            """
        ))

        conn.execute(text(
            """
            CREATE OR REPLACE VIEW vw_infra_escola_long AS
            SELECT
                ano              AS "NU_ANO_CENSO",
                uf               AS "SG_UF",
                cod_municipio    AS "CO_MUNICIPIO",
                nome_municipio   AS "NO_MUNICIPIO",
                tp_dependencia   AS "TP_DEPENDENCIA",
                rede_tipo        AS "REDE_TIPO",
                tp_localizacao   AS "TP_LOCALIZACAO",
                localizacao_tipo AS "LOCALIZACAO_TIPO",
                cod_escola       AS "CO_ENTIDADE",
                nome_escola      AS "NO_ENTIDADE",
                grupo_infra      AS "GrupoInfra",
                item             AS "Item",
                possui           AS "POSSUI"
            FROM fact_infra_escola;
            """
        ))

        conn.execute(text(
            """
            CREATE OR REPLACE VIEW vw_dados_indigena_normalizado AS
            SELECT
                ano            AS "NU_ANO_CENSO",
                uf             AS "SG_UF",
                cod_municipio  AS "CO_MUNICIPIO",
                nome_municipio AS "NO_MUNICIPIO",
                tp_dependencia AS "TP_DEPENDENCIA",
                tp_localizacao AS "TP_LOCALIZACAO",
                cod_escola     AS "CO_ENTIDADE",
                nome_escola    AS "NO_ENTIDADE",
                categoria      AS "CategoriaIndigena",
                grupo          AS "Grupo",
                etapa          AS "Etapa",
                qt             AS "QT"
            FROM fact_indigena;
            """
        ))

        conn.execute(text(
            """
            CREATE OR REPLACE VIEW vw_tx_rendimento_long AS
            SELECT
                ano                AS "Ano",
                regiao             AS "Região",
                uf                 AS "UF",
                cod_municipio      AS "Código do Município",
                nome_municipio     AS "Nome do Município",
                cod_escola         AS "Código da Escola",
                nome_escola        AS "Nome da Escola",
                localizacao        AS "Localização",
                dependencia        AS "Dependência Administrativa",
                etapa              AS "Etapa",
                serie              AS "Serie",
                metrica            AS "Métrica",
                valor              AS "Valor",
                valor_num          AS "Valor_num",
                valor_prop         AS "Valor_prop"
            FROM fact_tx_rendimento;
            """
        ))

        # 5. NOVA VIEW: SIOPE ORGANIZADO (EXPLODINDO O JSONB)
        conn.execute(text("""
            CREATE OR REPLACE VIEW vw_siope_detalhado AS
            SELECT 
                -- Colunas da Tabela
                id,
                num_ano,
                num_peri,
                sig_uf,
                cod_muni,
                periodo_label,
                
                -- Identificação e Localização (JSON)
                payload->>'TIPO' AS tipo_ente,
                payload->>'NOM_MUNI' AS nome_municipio,
                payload->>'SIG_UF' AS uf_payload,
                (payload->>'COD_UF')::INT AS cod_uf,
                (payload->>'COD_MUNI')::NUMERIC AS cod_muni_payload,
                
                -- Datas e Status
                payload->>'DAT_DECL' AS data_declaracao,
                payload->>'IDN_DECL_RETI' AS ind_declaracao_retificadora,
                payload->>'IDN_TIPO_DECL' AS tipo_declaracao,
                payload->>'DS_JUST_RETIFICACAO' AS justificativa_retificacao,
                
                -- População e PIB
                (payload->>'NUM_POPU')::NUMERIC AS populacao,
                (payload->>'VAL_PIB')::NUMERIC AS valor_pib,
                (payload->>'VAL_PIB_PERCAPTO')::NUMERIC AS valor_pib_percapto,
                
                -- Receitas (Geral e Fundeb)
                (payload->>'VAL_RECE_ORCA')::NUMERIC AS valor_receita_orcamentaria,
                (payload->>'VAL_RECE_REAL')::NUMERIC AS valor_receita_realizada,
                (payload->>'VAL_RECE_PREV_ATUA')::NUMERIC AS valor_receita_prevista_atualizada,
                (payload->>'NUM_FPM')::NUMERIC AS valor_fpm,
                (payload->>'NUM_FPE')::NUMERIC AS valor_fpe,
                (payload->>'NUM_ITR')::NUMERIC AS valor_itr,
                (payload->>'NUM_ICMS')::NUMERIC AS valor_icms,
                (payload->>'NUM_IPI_EXPO')::NUMERIC AS valor_ipi_exportacao,
                (payload->>'NUM_CIDE')::NUMERIC AS valor_cide,
                (payload->>'NUM_FUNDEF')::NUMERIC AS valor_fundeb,
                (payload->>'NUM_CP_FUNDEF')::NUMERIC AS valor_cp_fundeb,
                (payload->>'NUM_IPVA_FUNDEB')::NUMERIC AS valor_ipva_fundeb,
                (payload->>'NUM_ITCMD_FUNDEB')::NUMERIC AS valor_itcmd_fundeb,
                (payload->>'VAL_TRANSMISSAO')::NUMERIC AS valor_transmissao,
                
                -- Despesas Gerais (Dotação, Empenhado, Liquidado, Pago)
                (payload->>'VAL_DESP_ORCA')::NUMERIC AS valor_despesa_orcamentaria,
                (payload->>'VAL_DESP_DOTA_ATUA')::NUMERIC AS valor_despesa_dotacao_atualizada,
                (payload->>'VAL_DESP_EMPE')::NUMERIC AS valor_despesa_empenhada,
                (payload->>'VAL_DESP_LIQU')::NUMERIC AS valor_despesa_liquidada,
                (payload->>'VAL_DESP_PAGA')::NUMERIC AS valor_despesa_paga,
                
                -- Despesas Específicas de EDUCAÇÃO
                (payload->>'VL_DESP_ORCA_EDU')::NUMERIC AS valor_despesa_orcamentaria_edu,
                (payload->>'VL_DESP_DOTA_ATUA_EDU')::NUMERIC AS valor_despesa_dotacao_atualizada_edu,
                (payload->>'VL_DESP_EMPE_EDU')::NUMERIC AS valor_despesa_empenhada_edu,
                (payload->>'VL_DESP_LIQU_EDU')::NUMERIC AS valor_despesa_liquidada_edu,
                (payload->>'VL_DESP_PAGA_EDU')::NUMERIC AS valor_despesa_paga_edu,
                
                -- Indicadores e Metodologias
                payload->>'IDN_POSS_CERT_TC' AS possui_certidao_tc,
                payload->>'IDN_POSS_DECI_JUDI' AS possui_decisao_judicial,
                payload->>'IDN_METO_SIOPE_IGUA_TC' AS meto_siope_igual_tc,
                payload->>'IDN_METO_LIMI_CONS' AS meto_limite_constitucional,
                payload->>'IDN_ASSU_RESP_MTDO_APUR' AS assumiu_resp_metodo_apuracao,
                payload->>'DES_DIFE_METO_CALC' AS desc_diferenca_metodo_calculo,
                payload->>'DES_JUST_PROB_BALA' AS desc_justificativa_problema_balanco,
                
                -- Notas de Rodapé
                payload->>'DS_NOTA_RODAPE_RREO' AS nota_rodape_rreo,
                payload->>'DS_NOTA_RODAPE_FUNDEB' AS nota_rodape_fundeb,
                
                -- Outros
                payload->>'COD_DIGIT' AS cod_digitador,
                payload->>'COD_VERIFIC' AS cod_verificador,
                (payload->>'NUM_RECI')::NUMERIC AS num_recibo,
                (payload->>'NUM_SOLI')::NUMERIC AS num_solicitacao,
                (payload->>'NUM_PERI')::INT AS num_periodo_payload

            FROM siope_registro_raw;
        """))




# ======== UPSERT DIMENSÕES ========
def upsert_municipios_from_df(df: pd.DataFrame):
    if df is None or df.empty:
        return
    cols_map = {
        "CO_MUNICIPIO": "cod_municipio",
        "NO_MUNICIPIO": "nome",
        "SG_UF": "uf",
    }
    miss = [c for c in cols_map if c not in df.columns]
    if miss:
        return
    dfu = df[["CO_MUNICIPIO", "NO_MUNICIPIO", "SG_UF"]].drop_duplicates()
    rows = []
    for a, b, c in dfu.itertuples(index=False):
        ca = str(a) if pd.notna(a) and str(a) != "" else None
        if not ca:
            continue  # ignora linhas sem PK
        rows.append((
            ca,
            str(b) if pd.notna(b) else None,
            str(c) if pd.notna(c) else None,
        ))
    if not rows:
        return
    eng = get_engine()
    sql = (
        "INSERT INTO dim_municipio (cod_municipio, nome, uf) "
        "VALUES (:0, :1, :2) "
        "ON CONFLICT (cod_municipio) DO UPDATE SET nome = EXCLUDED.nome, uf = EXCLUDED.uf"
    )
    with eng.begin() as conn:
        _exec_batch(conn, sql, rows)


def upsert_escolas_from_df(df: pd.DataFrame):
    if df is None or df.empty:
        return
    miss = [c for c in ("CO_ENTIDADE", "NO_ENTIDADE", "CO_MUNICIPIO") if c not in df.columns]
    if miss:
        return
    dfu = df[["CO_ENTIDADE", "NO_ENTIDADE", "CO_MUNICIPIO"]].drop_duplicates()
    rows = []
    for a, b, c in dfu.itertuples(index=False):
        ce = str(a) if pd.notna(a) and str(a) != "" else None
        if not ce:
            continue  # ignora linhas sem PK
        rows.append((
            ce,
            str(b) if pd.notna(b) else None,
            str(c) if pd.notna(c) else None,
        ))
    if not rows:
        return
    eng = get_engine()
    sql = (
        "INSERT INTO dim_escola (cod_escola, nome, cod_municipio) "
        "VALUES (:0, :1, :2) "
        "ON CONFLICT (cod_escola) DO UPDATE SET nome = EXCLUDED.nome, cod_municipio = EXCLUDED.cod_municipio"
    )
    with eng.begin() as conn:
        _exec_batch(conn, sql, rows)


# ======== INSERÇÃO DE FATO ========
def insert_censo_medidas(df_long: pd.DataFrame):
    if df_long is None or df_long.empty:
        return
    req = [
        "NU_ANO_CENSO", "SG_UF", "CO_MUNICIPIO", "NO_MUNICIPIO",
        "TP_DEPENDENCIA", "TP_LOCALIZACAO", "CO_ENTIDADE", "NO_ENTIDADE",
        "Grupo", "Etapa", "QT",
    ]
    miss = [c for c in req if c not in df_long.columns]
    if miss:
        return
    dfu = df_long[req].copy()
    rows = [
        (
            int(a) if pd.notna(a) else None,
            str(b) if pd.notna(b) else None,
            str(c) if pd.notna(c) else None,
            str(d) if pd.notna(d) else None,
            str(e) if pd.notna(e) else None,
            str(f) if pd.notna(f) else None,
            str(g) if pd.notna(g) else None,
            str(h) if pd.notna(h) else None,
            str(i) if pd.notna(i) else None,
            str(j) if pd.notna(j) else None,
            int(k) if (pd.notna(k) and k != "") else None,
        )
        for a, b, c, d, e, f, g, h, i, j, k in dfu.itertuples(index=False)
    ]
    eng = get_engine()
    sql = (
        "INSERT INTO fact_censo_medida (ano, uf, cod_municipio, nome_municipio, tp_dependencia, tp_localizacao, "
        "cod_escola, nome_escola, grupo, etapa, qt) VALUES "
        "(:0,:1,:2,:3,:4,:5,:6,:7,:8,:9,:10) "
        "ON CONFLICT (ano, cod_escola, grupo, etapa) DO UPDATE SET qt = EXCLUDED.qt, "
        "uf=EXCLUDED.uf, cod_municipio=EXCLUDED.cod_municipio, nome_municipio=EXCLUDED.nome_municipio, "
        "tp_dependencia=EXCLUDED.tp_dependencia, tp_localizacao=EXCLUDED.tp_localizacao, nome_escola=EXCLUDED.nome_escola"
    )
    with eng.begin() as conn:
        _exec_batch(conn, sql, rows)


def insert_infra_escola(df_long: pd.DataFrame):
    if df_long is None or df_long.empty:
        return
    req = [
        "NU_ANO_CENSO","SG_UF","CO_MUNICIPIO","NO_MUNICIPIO",
        "TP_DEPENDENCIA","REDE_TIPO","TP_LOCALIZACAO","LOCALIZACAO_TIPO",
        "CO_ENTIDADE","NO_ENTIDADE","GrupoInfra","Item","POSSUI"
    ]
    miss = [c for c in req if c not in df_long.columns]
    if miss:
        return
    dfu = df_long[req].copy()
    rows = [
        (
            int(a) if pd.notna(a) else None,
            str(b) if pd.notna(b) else None,
            str(c) if pd.notna(c) else None,
            str(d) if pd.notna(d) else None,
            str(e) if pd.notna(e) else None,
            str(f) if pd.notna(f) else None,
            str(g) if pd.notna(g) else None,
            str(h) if pd.notna(h) else None,
            str(i) if pd.notna(i) else None,
            str(j) if pd.notna(j) else None,
            str(k) if pd.notna(k) else None,
            str(l) if pd.notna(l) else None,
            int(m) if pd.notna(m) else None,
        )
        for a,b,c,d,e,f,g,h,i,j,k,l,m in dfu.itertuples(index=False)
    ]
    eng = get_engine()
    sql = (
        "INSERT INTO fact_infra_escola (ano, uf, cod_municipio, nome_municipio, tp_dependencia, rede_tipo, tp_localizacao, localizacao_tipo, "
        "cod_escola, nome_escola, grupo_infra, item, possui) VALUES "
        "(:0,:1,:2,:3,:4,:5,:6,:7,:8,:9,:10,:11,:12) "
        "ON CONFLICT (ano, cod_escola, item) DO UPDATE SET possui = EXCLUDED.possui, "
        "uf=EXCLUDED.uf, cod_municipio=EXCLUDED.cod_municipio, nome_municipio=EXCLUDED.nome_municipio, "
        "tp_dependencia=EXCLUDED.tp_dependencia, rede_tipo=EXCLUDED.rede_tipo, tp_localizacao=EXCLUDED.tp_localizacao, "
        "localizacao_tipo=EXCLUDED.localizacao_tipo, nome_escola=EXCLUDED.nome_escola, grupo_infra=EXCLUDED.grupo_infra"
    )
    with eng.begin() as conn:
        _exec_batch(conn, sql, rows)


def insert_indigena(df_long: pd.DataFrame):
    if df_long is None or df_long.empty:
        return
    req = [
        "NU_ANO_CENSO","SG_UF","CO_MUNICIPIO","NO_MUNICIPIO",
        "TP_DEPENDENCIA","TP_LOCALIZACAO","CO_ENTIDADE","NO_ENTIDADE",
        "CategoriaIndigena","Grupo","Etapa","QT"
    ]
    miss = [c for c in req if c not in df_long.columns]
    if miss:
        return
    dfu = df_long[req].copy()
    rows = []
    for a,b,c,d,e,f,g,h,i,j,k,l in dfu.itertuples(index=False):
        rows.append((
            int(a) if pd.notna(a) else None,
            str(b) if pd.notna(b) else None,
            str(c) if pd.notna(c) else None,
            str(d) if pd.notna(d) else None,
            str(e) if pd.notna(e) else None,
            str(f) if pd.notna(f) else None,
            str(g) if pd.notna(g) else None,
            str(h) if pd.notna(h) else None,
            str(i) if pd.notna(i) else None,
            str(j) if pd.notna(j) else None,
            str(k) if pd.notna(k) else None,
            int(l) if pd.notna(l) else None,
        ))
    eng = get_engine()
    sql = (
        "INSERT INTO fact_indigena (ano, uf, cod_municipio, nome_municipio, tp_dependencia, tp_localizacao, "
        "cod_escola, nome_escola, categoria, grupo, etapa, qt) VALUES "
        "(:0,:1,:2,:3,:4,:5,:6,:7,:8,:9,:10,:11) "
        "ON CONFLICT (ano, cod_escola, categoria, grupo, etapa) DO UPDATE SET qt = EXCLUDED.qt, "
        "uf=EXCLUDED.uf, cod_municipio=EXCLUDED.cod_municipio, nome_municipio=EXCLUDED.nome_municipio, "
        "tp_dependencia=EXCLUDED.tp_dependencia, tp_localizacao=EXCLUDED.tp_localizacao, nome_escola=EXCLUDED.nome_escola"
    )
    with eng.begin() as conn:
        _exec_batch(conn, sql, rows)


def insert_tx_rendimento(df_long: pd.DataFrame):
    if df_long is None or df_long.empty:
        return
    # Aceita colunas parciais; preenche None quando ausentes.
    cols = {
        "ano": "Ano",
        "regiao": "Região",
        "uf": "UF",
        "cod_municipio": "Código do Município",
        "nome_municipio": "Nome do Município",
        "cod_escola": "Código da Escola",
        "nome_escola": "Nome da Escola",
        "localizacao": "Localização",
        "dependencia": "Dependência Administrativa",
        "etapa": "Etapa",
        "serie": "Serie",
        "metrica": "Métrica",
        "valor": "Valor",
        "valor_num": "Valor_num",
        "valor_prop": "Valor_prop",
    }
    recs = df_long.to_dict(orient="records")
    rows = []
    for r in recs:
        def g(key):
            col = cols[key]
            return r.get(col, None)
        rows.append((
            _to_int_or_none(g("ano")),
            (str(g("regiao")) if pd.notna(g("regiao")) else None),
            (str(g("uf")) if pd.notna(g("uf")) else None),
            (str(g("cod_municipio")) if pd.notna(g("cod_municipio")) else None),
            (str(g("nome_municipio")) if pd.notna(g("nome_municipio")) else None),
            (str(g("cod_escola")) if (pd.notna(g("cod_escola")) and str(g("cod_escola")) != "") else None),
            (str(g("nome_escola")) if (pd.notna(g("nome_escola")) and str(g("nome_escola")) != "") else None),
            (str(g("localizacao")) if pd.notna(g("localizacao")) else None),
            (str(g("dependencia")) if pd.notna(g("dependencia")) else None),
            (str(g("etapa")) if pd.notna(g("etapa")) else None),
            _to_int_or_none(g("serie")),
            (str(g("metrica")) if pd.notna(g("metrica")) else None),
            (str(g("valor")) if pd.notna(g("valor")) else None),
            _to_float_or_none(g("valor_num")),
            _to_float_or_none(g("valor_prop")),
        ))
    eng = get_engine()
    sql = (
        "INSERT INTO fact_tx_rendimento (ano, regiao, uf, cod_municipio, nome_municipio, cod_escola, nome_escola, "
        "localizacao, dependencia, etapa, serie, metrica, valor, valor_num, valor_prop) VALUES "
        "(:0,:1,:2,:3,:4,:5,:6,:7,:8,:9,:10,:11,:12,:13,:14) "
        "ON CONFLICT (ano, uf, cod_municipio, cod_escola, etapa, serie, metrica) DO UPDATE SET "
        "valor = EXCLUDED.valor, valor_num = EXCLUDED.valor_num, valor_prop = EXCLUDED.valor_prop, "
        "regiao=EXCLUDED.regiao, nome_municipio=EXCLUDED.nome_municipio, nome_escola=EXCLUDED.nome_escola, "
        "localizacao=EXCLUDED.localizacao, dependencia=EXCLUDED.dependencia"
    )
    with eng.begin() as conn:
        _exec_batch(conn, sql, rows)


def insert_siope_raw(df: pd.DataFrame):
    if df is None or df.empty:
        return
    # colunas usuais se existirem
    has = {c: c in df.columns for c in ["NUM_ANO","NUM_PERI","SIG_UF","COD_MUNI","PERIODO_LABEL"]}
    # prepara rows como dicts nomeados + json payload (string)
    def _muni_str(v):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        try:
            # remove .0 quando vier float
            iv = int(float(v))
            return str(iv)
        except Exception:
            return str(v)

    rows = []
    for _, row in df.iterrows():
        rows.append({
            "num_ano": int(row["NUM_ANO"]) if has["NUM_ANO"] and pd.notna(row["NUM_ANO"]) else None,
            "num_peri": int(row["NUM_PERI"]) if has["NUM_PERI"] and pd.notna(row["NUM_PERI"]) else None,
            "sig_uf": str(row["SIG_UF"]) if has["SIG_UF"] and pd.notna(row["SIG_UF"]) else None,
            "cod_muni": _muni_str(row["COD_MUNI"]) if has["COD_MUNI"] else None,
            "periodo_label": str(row["PERIODO_LABEL"]) if has["PERIODO_LABEL"] and pd.notna(row["PERIODO_LABEL"]) else None,
            # envia como estrutura Python para adaptação JSON via SQLAlchemy
            "payload": json.loads(row.to_json()),
        })
    eng = get_engine()
    sql = (
        "INSERT INTO siope_registro_raw (num_ano, num_peri, sig_uf, cod_muni, periodo_label, payload) "
        "VALUES (:num_ano,:num_peri,:sig_uf,:cod_muni,:periodo_label, :payload)"
    )
    with eng.begin() as conn:
        stmt = text(sql).bindparams(bindparam("payload", type_=JSON))
        _exec_batch(conn, stmt, rows, chunk=1000)
