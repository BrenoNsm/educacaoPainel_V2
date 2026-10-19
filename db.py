"""
db.py
Utilitários de persistência em PostgreSQL para o pipeline.
Modelo estrela (star schema) para BI.

Dimensões:
  dim_tempo, dim_localizacao, dim_dependencia, dim_grupo_medida,
  dim_grupo_infra, dim_categoria_indigena, dim_metrica,
  dim_tipo_receita, dim_tipo_despesa, dim_municipio, dim_escola

Fatos:
  fact_censo_medida, fact_infra_escola, fact_indigena,
  fact_tx_rendimento, fact_siope_receita, fact_siope_despesa,
  fact_siope_indicadores
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


# ═══════════════════════════════════════════════════════════════
# MAPAS DE DOMÍNIO (chave natural → rótulo legível)
# ═══════════════════════════════════════════════════════════════

REGIOES = {
    "AC": "Norte", "AM": "Norte", "AP": "Norte", "PA": "Norte",
    "RO": "Norte", "RR": "Norte", "TO": "Norte",
    "AL": "Nordeste", "BA": "Nordeste", "CE": "Nordeste",
    "MA": "Nordeste", "PB": "Nordeste", "PE": "Nordeste",
    "PI": "Nordeste", "RN": "Nordeste", "SE": "Nordeste",
    "DF": "Centro-Oeste", "GO": "Centro-Oeste", "MS": "Centro-Oeste", "MT": "Centro-Oeste",
    "ES": "Sudeste", "MG": "Sudeste", "RJ": "Sudeste", "SP": "Sudeste",
    "PR": "Sul", "RS": "Sul", "SC": "Sul",
}

DEPENDENCIA_MAP = {
    "1": ("1", "Federal"), "FEDERAL": ("1", "Federal"),
    "2": ("2", "Estadual"), "ESTADUAL": ("2", "Estadual"), "ESTADO": ("2", "Estadual"),
    "3": ("3", "Municipal"), "MUNICIPAL": ("3", "Municipal"), "MUNICÍPAL": ("3", "Municipal"),
    "4": ("4", "Privada"), "PRIVADA": ("4", "Privada"), "PARTICULAR": ("4", "Privada"),
}

LOCALIZACAO_MAP = {
    "1": ("1", "Urbana"), "URBANA": ("1", "Urbana"), "URBANO": ("1", "Urbana"),
    "2": ("2", "Rural"), "RURAL": ("2", "Rural"),
}

GRUPOS_MEDIDA_SEED = [
    ("Matrículas", "Educação Especial"),
    ("Matrículas", "Ed. Infantil - Creche"),
    ("Matrículas", "Ed. Infantil - Pré-Escola"),
    ("Matrículas", "Ensino Fund. - Anos Iniciais"),
    ("Matrículas", "Ensino Fund. - Anos Finais"),
    ("Matrículas", "Ensino Médio"),
    ("Matrículas", "EJA - Ensino Fundamental"),
    ("Matrículas", "EJA - Ensino Médio"),
    ("Matrículas - Tempo Integral", "Ed. Infantil - Creche"),
    ("Matrículas - Tempo Integral", "Ed. Infantil - Pré-Escola"),
    ("Matrículas - Tempo Integral", "Ensino Fund. - Anos Iniciais"),
    ("Matrículas - Tempo Integral", "Ensino Fund. - Anos Finais"),
    ("Matrículas - Tempo Integral", "Ensino Médio"),
    ("Turmas", "Educação Especial"),
    ("Turmas", "Ed. Infantil - Creche"),
    ("Turmas", "Ed. Infantil - Pré-Escola"),
    ("Turmas", "Ensino Fund. - Anos Iniciais"),
    ("Turmas", "Ensino Fund. - Anos Finais"),
    ("Turmas", "Ensino Médio"),
    ("Turmas", "EJA - Ensino Fundamental"),
    ("Turmas", "EJA - Ensino Médio"),
    ("Docentes", "Educação Básica (Total)"),
    ("Docentes", "Educação Especial"),
    ("Docentes", "Ed. Infantil - Creche"),
    ("Docentes", "Ed. Infantil - Pré-Escola"),
    ("Docentes", "Ensino Fund. - Anos Iniciais"),
    ("Docentes", "Ensino Fund. - Anos Finais"),
    ("Docentes", "Ensino Médio"),
    ("Docentes", "EJA - Ensino Fundamental"),
    ("Docentes", "EJA - Ensino Médio"),
    ("Docentes (Estimado)", "Educação Especial"),
    ("Docentes (Estimado)", "Ed. Infantil - Creche"),
    ("Docentes (Estimado)", "Ed. Infantil - Pré-Escola"),
    ("Docentes (Estimado)", "Ensino Fund. - Anos Iniciais"),
    ("Docentes (Estimado)", "Ensino Fund. - Anos Finais"),
    ("Docentes (Estimado)", "Ensino Médio"),
    ("Docentes (Estimado)", "EJA - Ensino Fundamental"),
    ("Docentes (Estimado)", "EJA - Ensino Médio"),
    ("Escolas", "Todas"),
    ("Matrículas Indígenas (Total)", "Todas"),
    ("Matrículas Indígenas (Etapas)", "Educação Especial"),
    ("Matrículas Indígenas (Etapas)", "Ed. Infantil - Creche"),
    ("Matrículas Indígenas (Etapas)", "Ed. Infantil - Pré-Escola"),
    ("Matrículas Indígenas (Etapas)", "Ensino Fund. - Anos Iniciais"),
    ("Matrículas Indígenas (Etapas)", "Ensino Fund. - Anos Finais"),
    ("Matrículas Indígenas (Etapas)", "Ensino Médio"),
    ("Matrículas Indígenas (Etapas)", "EJA - Ensino Fundamental"),
    ("Matrículas Indígenas (Etapas)", "EJA - Ensino Médio"),
    ("Matrículas Indígenas (Etapas)", "Não detalhado"),
    ("Matrículas (GERAL)", "Educação Especial"),
    ("Matrículas (GERAL)", "Ed. Infantil - Creche"),
    ("Matrículas (GERAL)", "Ed. Infantil - Pré-Escola"),
    ("Matrículas (GERAL)", "Ensino Fund. - Anos Iniciais"),
    ("Matrículas (GERAL)", "Ensino Fund. - Anos Finais"),
    ("Matrículas (GERAL)", "Ensino Médio"),
    ("Matrículas (GERAL)", "EJA - Ensino Fundamental"),
    ("Matrículas (GERAL)", "EJA - Ensino Médio"),
]

GRUPOS_INFRA_SEED = [
    "Água", "Energia", "Esgoto", "Lixo",
    "Internet/TIC", "Dependências", "Acessibilidade", "Outros",
]

CATEGORIAS_INDIGENA_SEED = [
    "Escola Indígena", "Em Terra Indígena", "Com Língua Indígena", "Não indígena",
]

METRICAS_RENDIMENTO_SEED = [
    "Taxa de Aprovação", "Taxa de Reprovação", "Taxa de Abandono",
]

TIPOS_RECEITA_SEED = [
    ("RECEITA_ORCAMENTARIA", "Receita Orçamentária", "Receita"),
    ("RECEITA_REALIZADA", "Receita Realizada", "Receita"),
    ("RECEITA_PREVISTA_ATUALIZADA", "Receita Prevista Atualizada", "Receita"),
    ("FPM", "Fundo de Partilha do Minas", "Transferência"),
    ("FPE", "Fundo de Participação dos Estados", "Transferência"),
    ("ITR", "Imposto Territorial Rural", "Imposto"),
    ("ICMS", "ICMS", "Imposto"),
    ("IPI_EXPORTACAO", "IPI de Exportação", "Imposto"),
    ("CIDE", "CIDE", "Imposto"),
    ("FUNDEB", "FUNDEB", "FUNDEB"),
    ("CP_FUNDEB", "Cota-Parte FUNDEB", "FUNDEB"),
    ("IPVA_FUNDEB", "IPVA para FUNDEB", "FUNDEB"),
    ("ITCMD_FUNDEB", "ITCMD para FUNDEB", "FUNDEB"),
    ("TRANSMISSAO", "Transmissão", "Receita"),
]

TIPOS_DESPESA_SEED = [
    ("GERAL_ORCAMENTARIA", "Despesa Orçamentária", "Geral"),
    ("GERAL_DOTACAO_ATUALIZADA", "Despesa Dotação Atualizada", "Geral"),
    ("GERAL_EMPENHADA", "Despesa Empenhada", "Geral"),
    ("GERAL_LIQUIDADA", "Despesa Liquidada", "Geral"),
    ("GERAL_PAGA", "Despesa Paga", "Geral"),
    ("EDU_ORCAMENTARIA", "Despesa Orçamentária Educação", "Educação"),
    ("EDU_DOTACAO_ATUALIZADA", "Despesa Dotação Atualizada Educação", "Educação"),
    ("EDU_EMPENHADA", "Despesa Empenhada Educação", "Educação"),
    ("EDU_LIQUIDADA", "Despesa Liquidada Educação", "Educação"),
    ("EDU_PAGA", "Despesa Paga Educação", "Educação"),
]

SIOPE_RECEITA_KEYS = {
    "VAL_RECE_ORCA": "RECEITA_ORCAMENTARIA",
    "VAL_RECE_REAL": "RECEITA_REALIZADA",
    "VAL_RECE_PREV_ATUA": "RECEITA_PREVISTA_ATUALIZADA",
    "NUM_FPM": "FPM", "NUM_FPE": "FPE", "NUM_ITR": "ITR",
    "NUM_ICMS": "ICMS", "NUM_IPI_EXPO": "IPI_EXPORTACAO",
    "NUM_CIDE": "CIDE", "NUM_FUNDEF": "FUNDEB",
    "NUM_CP_FUNDEF": "CP_FUNDEB", "NUM_IPVA_FUNDEB": "IPVA_FUNDEB",
    "NUM_ITCMD_FUNDEB": "ITCMD_FUNDEB", "VAL_TRANSMISSAO": "TRANSMISSAO",
}

SIOPE_DESPESA_KEYS = {
    "VAL_DESP_ORCA": "GERAL_ORCAMENTARIA",
    "VAL_DESP_DOTA_ATUA": "GERAL_DOTACAO_ATUALIZADA",
    "VAL_DESP_EMPE": "GERAL_EMPENHADA",
    "VAL_DESP_LIQU": "GERAL_LIQUIDADA",
    "VAL_DESP_PAGA": "GERAL_PAGA",
    "VL_DESP_ORCA_EDU": "EDU_ORCAMENTARIA",
    "VL_DESP_DOTA_ATUA_EDU": "EDU_DOTACAO_ATUALIZADA",
    "VL_DESP_EMPE_EDU": "EDU_EMPENHADA",
    "VL_DESP_LIQU_EDU": "EDU_LIQUIDADA",
    "VL_DESP_PAGA_EDU": "EDU_PAGA",
}


# ═══════════════════════════════════════════════════════════════
# UTILITÁRIOS
# ═══════════════════════════════════════════════════════════════

def _to_int_or_none(v):
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


def _s(v):
    """Converte para string, None se vazio/NaN."""
    if v is None:
        return None
    try:
        if isinstance(v, float) and math.isnan(v):
            return None
    except Exception:
        pass
    s = str(v).strip()
    return s if s != "" and s.lower() != "nan" else None


def _i(v):
    """Converte para int, None se vazio/NaN."""
    return _to_int_or_none(v)


def _get(row, *candidates):
    """Busca o primeiro valor não-nulo entre nomes de coluna candidatos."""
    for c in candidates:
        if c in row.index:
            v = row[c]
            if pd.notna(v):
                return v
    return None


def _exec_batch(conn, sql, rows: Sequence, chunk: int = 5000):
    """Execute bateladas com SQLAlchemy 2.0."""
    if not rows:
        return
    total = len(rows)
    try:
        from sqlalchemy.sql.elements import TextClause
        stmt = sql if isinstance(sql, TextClause) else text(sql)
    except Exception:
        stmt = text(sql)
    for i in range(0, total, chunk):
        part = rows[i: i + chunk]
        if part and not isinstance(part[0], dict):
            dicts = []
            for row in part:
                d = {str(j): v for j, v in enumerate(row)}
                dicts.append(d)
        else:
            dicts = part
        conn.execute(stmt, dicts)


# ═══════════════════════════════════════════════════════════════
# ENGINE
# ═══════════════════════════════════════════════════════════════

def get_engine():
    global _ENGINE
    if _ENGINE is None:
        url = (
            f"postgresql+psycopg://{config.PG_USER}:{config.PG_PASSWORD}"
            f"@{config.PG_HOST}:{config.PG_PORT}/{config.PG_DATABASE}"
        )
        _ENGINE = create_engine(url, pool_pre_ping=True, future=True)
    return _ENGINE


# ═══════════════════════════════════════════════════════════════
# DDL (IDEMPOTENTE)
# ═══════════════════════════════════════════════════════════════

def init_db():
    """Cria todas as tabelas, popula dimensões seed e cria views."""
    eng = get_engine()
    with eng.begin() as conn:

        # ── DIMENSÕES ──────────────────────────────────────────
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS dim_tempo (
                sk_tempo  SERIAL PRIMARY KEY,
                ano       INT NOT NULL UNIQUE
            );
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS dim_localizacao (
                sk_localizacao  SERIAL PRIMARY KEY,
                cod_localizacao TEXT NOT NULL UNIQUE,
                descricao       TEXT NOT NULL
            );
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS dim_dependencia (
                sk_dependencia  SERIAL PRIMARY KEY,
                cod_dependencia TEXT NOT NULL UNIQUE,
                descricao       TEXT NOT NULL
            );
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS dim_grupo_medida (
                sk_grupo_medida SERIAL PRIMARY KEY,
                grupo           TEXT NOT NULL,
                etapa           TEXT NOT NULL,
                UNIQUE(grupo, etapa)
            );
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS dim_grupo_infra (
                sk_grupo_infra SERIAL PRIMARY KEY,
                grupo_infra    TEXT NOT NULL UNIQUE
            );
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS dim_categoria_indigena (
                sk_categoria_indigena SERIAL PRIMARY KEY,
                categoria             TEXT NOT NULL UNIQUE
            );
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS dim_metrica (
                sk_metrica SERIAL PRIMARY KEY,
                metrica    TEXT NOT NULL UNIQUE
            );
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS dim_tipo_receita (
                sk_tipo_receita SERIAL PRIMARY KEY,
                cod_receita     TEXT NOT NULL UNIQUE,
                descricao       TEXT,
                categoria       TEXT
            );
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS dim_tipo_despesa (
                sk_tipo_despesa SERIAL PRIMARY KEY,
                cod_despesa     TEXT NOT NULL UNIQUE,
                descricao       TEXT,
                categoria       TEXT
            );
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS dim_municipio (
                cod_municipio TEXT PRIMARY KEY,
                nome          TEXT,
                uf            TEXT,
                regiao        TEXT
            );
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS dim_escola (
                cod_escola     TEXT PRIMARY KEY,
                nome           TEXT,
                cod_municipio  TEXT REFERENCES dim_municipio(cod_municipio),
                sk_dependencia INT REFERENCES dim_dependencia(sk_dependencia),
                sk_localizacao INT REFERENCES dim_localizacao(sk_localizacao)
            );
        """))

        # Índices para dim_escola
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_dim_escola_municipio ON dim_escola(cod_municipio);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_dim_escola_depend   ON dim_escola(sk_dependencia);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_dim_escola_local    ON dim_escola(sk_localizacao);"))

        # ── FATOS ──────────────────────────────────────────────
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS siope_registro_raw (
                id             BIGSERIAL PRIMARY KEY,
                num_ano        INT,
                num_peri       INT,
                sig_uf         TEXT,
                cod_muni       TEXT,
                periodo_label  TEXT,
                payload        JSONB
            );
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS fact_censo_medida (
                sk_tempo        INT REFERENCES dim_tempo(sk_tempo),
                cod_escola      TEXT REFERENCES dim_escola(cod_escola),
                sk_grupo_medida INT REFERENCES dim_grupo_medida(sk_grupo_medida),
                qt              INT,
                PRIMARY KEY(sk_tempo, cod_escola, sk_grupo_medida)
            );
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS fact_infra_escola (
                sk_tempo       INT REFERENCES dim_tempo(sk_tempo),
                cod_escola     TEXT REFERENCES dim_escola(cod_escola),
                sk_grupo_infra INT REFERENCES dim_grupo_infra(sk_grupo_infra),
                item           TEXT,
                possui         INT,
                PRIMARY KEY(sk_tempo, cod_escola, item)
            );
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS fact_indigena (
                sk_tempo              INT REFERENCES dim_tempo(sk_tempo),
                cod_escola            TEXT REFERENCES dim_escola(cod_escola),
                sk_categoria_indigena INT REFERENCES dim_categoria_indigena(sk_categoria_indigena),
                sk_grupo_medida       INT REFERENCES dim_grupo_medida(sk_grupo_medida),
                qt                    INT,
                PRIMARY KEY(sk_tempo, cod_escola, sk_categoria_indigena, sk_grupo_medida)
            );
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS fact_tx_rendimento (
                sk_tempo      INT REFERENCES dim_tempo(sk_tempo),
                cod_municipio TEXT REFERENCES dim_municipio(cod_municipio),
                cod_escola    TEXT,
                sk_metrica    INT REFERENCES dim_metrica(sk_metrica),
                etapa         TEXT,
                serie         INT,
                valor         TEXT,
                valor_num     DOUBLE PRECISION,
                valor_prop    DOUBLE PRECISION,
                PRIMARY KEY(sk_tempo, cod_municipio, cod_escola, sk_metrica, etapa, serie)
            );
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS fact_siope_receita (
                sk_tempo        INT REFERENCES dim_tempo(sk_tempo),
                cod_municipio   TEXT REFERENCES dim_municipio(cod_municipio),
                sk_tipo_receita INT REFERENCES dim_tipo_receita(sk_tipo_receita),
                valor           NUMERIC,
                PRIMARY KEY(sk_tempo, cod_municipio, sk_tipo_receita)
            );
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS fact_siope_despesa (
                sk_tempo        INT REFERENCES dim_tempo(sk_tempo),
                cod_municipio   TEXT REFERENCES dim_municipio(cod_municipio),
                sk_tipo_despesa INT REFERENCES dim_tipo_despesa(sk_tipo_despesa),
                valor           NUMERIC,
                PRIMARY KEY(sk_tempo, cod_municipio, sk_tipo_despesa)
            );
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS fact_siope_indicadores (
                sk_tempo           INT REFERENCES dim_tempo(sk_tempo),
                cod_municipio      TEXT REFERENCES dim_municipio(cod_municipio),
                populacao          NUMERIC,
                valor_pib          NUMERIC,
                valor_pib_percapto NUMERIC,
                PRIMARY KEY(sk_tempo, cod_municipio)
            );
        """))

        # ── ÍNDICES AUXILIARES ─────────────────────────────────
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_fact_censo_escola   ON fact_censo_medida(cod_escola);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_fact_censo_tempo    ON fact_censo_medida(sk_tempo);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_fact_infra_escola  ON fact_infra_escola(cod_escola);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_fact_indig_escola  ON fact_indigena(cod_escola);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_fact_rend_escola   ON fact_tx_rendimento(cod_escola);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_fact_rend_mun     ON fact_tx_rendimento(cod_municipio);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_fact_siope_rec_mun ON fact_siope_receita(cod_municipio);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_fact_siope_des_mun ON fact_siope_despesa(cod_municipio);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_fact_siope_ind_mun ON fact_siope_indicadores(cod_municipio);"))

        # ── SEED DIMENSÕES ─────────────────────────────────────
        for cod, desc in [("1", "Urbana"), ("2", "Rural")]:
            conn.execute(text(
                "INSERT INTO dim_localizacao (cod_localizacao, descricao) VALUES (:c, :d) "
                "ON CONFLICT (cod_localizacao) DO NOTHING"
            ), {"c": cod, "d": desc})

        for cod, desc in [("1", "Federal"), ("2", "Estadual"), ("3", "Municipal"), ("4", "Privada")]:
            conn.execute(text(
                "INSERT INTO dim_dependencia (cod_dependencia, descricao) VALUES (:c, :d) "
                "ON CONFLICT (cod_dependencia) DO NOTHING"
            ), {"c": cod, "d": desc})

        for grupo, etapa in GRUPOS_MEDIDA_SEED:
            conn.execute(text(
                "INSERT INTO dim_grupo_medida (grupo, etapa) VALUES (:g, :e) "
                "ON CONFLICT (grupo, etapa) DO NOTHING"
            ), {"g": grupo, "e": etapa})

        for nome in GRUPOS_INFRA_SEED:
            conn.execute(text(
                "INSERT INTO dim_grupo_infra (grupo_infra) VALUES (:n) "
                "ON CONFLICT (grupo_infra) DO NOTHING"
            ), {"n": nome})

        for cat in CATEGORIAS_INDIGENA_SEED:
            conn.execute(text(
                "INSERT INTO dim_categoria_indigena (categoria) VALUES (:c) "
                "ON CONFLICT (categoria) DO NOTHING"
            ), {"c": cat})

        for met in METRICAS_RENDIMENTO_SEED:
            conn.execute(text(
                "INSERT INTO dim_metrica (metrica) VALUES (:m) "
                "ON CONFLICT (metrica) DO NOTHING"
            ), {"m": met})

        for cod, desc, cat in TIPOS_RECEITA_SEED:
            conn.execute(text(
                "INSERT INTO dim_tipo_receita (cod_receita, descricao, categoria) "
                "VALUES (:c, :d, :cat) ON CONFLICT (cod_receita) DO NOTHING"
            ), {"c": cod, "d": desc, "cat": cat})

        for cod, desc, cat in TIPOS_DESPESA_SEED:
            conn.execute(text(
                "INSERT INTO dim_tipo_despesa (cod_despesa, descricao, categoria) "
                "VALUES (:c, :d, :cat) ON CONFLICT (cod_despesa) DO NOTHING"
            ), {"c": cod, "d": desc, "cat": cat})

        # ── VIEWS (MODELO ESTRELA PARA BI) ─────────────────────
        conn.execute(text("""
            CREATE OR REPLACE VIEW vw_fact_censo AS
            SELECT
                t.ano,
                m.cod_municipio, m.nome AS nome_municipio, m.uf, m.regiao,
                e.cod_escola, e.nome AS nome_escola,
                d.descricao AS dependencia, l.descricao AS localizacao,
                gm.grupo, gm.etapa,
                f.qt
            FROM fact_censo_medida f
            JOIN dim_tempo t           ON f.sk_tempo = t.sk_tempo
            JOIN dim_escola e          ON f.cod_escola = e.cod_escola
            JOIN dim_municipio m       ON e.cod_municipio = m.cod_municipio
            JOIN dim_grupo_medida gm   ON f.sk_grupo_medida = gm.sk_grupo_medida
            JOIN dim_dependencia d     ON e.sk_dependencia = d.sk_dependencia
            JOIN dim_localizacao l     ON e.sk_localizacao = l.sk_localizacao;
        """))

        conn.execute(text("""
            CREATE OR REPLACE VIEW vw_fact_infra AS
            SELECT
                t.ano,
                m.cod_municipio, m.nome AS nome_municipio, m.uf, m.regiao,
                e.cod_escola, e.nome AS nome_escola,
                d.descricao AS dependencia, l.descricao AS localizacao,
                gi.grupo_infra, f.item, f.possui
            FROM fact_infra_escola f
            JOIN dim_tempo t           ON f.sk_tempo = t.sk_tempo
            JOIN dim_escola e          ON f.cod_escola = e.cod_escola
            JOIN dim_municipio m       ON e.cod_municipio = m.cod_municipio
            JOIN dim_grupo_infra gi    ON f.sk_grupo_infra = gi.sk_grupo_infra
            JOIN dim_dependencia d     ON e.sk_dependencia = d.sk_dependencia
            JOIN dim_localizacao l     ON e.sk_localizacao = l.sk_localizacao;
        """))

        conn.execute(text("""
            CREATE OR REPLACE VIEW vw_fact_indigena AS
            SELECT
                t.ano,
                m.cod_municipio, m.nome AS nome_municipio, m.uf, m.regiao,
                e.cod_escola, e.nome AS nome_escola,
                d.descricao AS dependencia, l.descricao AS localizacao,
                ci.categoria, gm.grupo, gm.etapa,
                f.qt
            FROM fact_indigena f
            JOIN dim_tempo t              ON f.sk_tempo = t.sk_tempo
            JOIN dim_escola e             ON f.cod_escola = e.cod_escola
            JOIN dim_municipio m          ON e.cod_municipio = m.cod_municipio
            JOIN dim_categoria_indigena ci ON f.sk_categoria_indigena = ci.sk_categoria_indigena
            JOIN dim_grupo_medida gm      ON f.sk_grupo_medida = gm.sk_grupo_medida
            JOIN dim_dependencia d        ON e.sk_dependencia = d.sk_dependencia
            JOIN dim_localizacao l        ON e.sk_localizacao = l.sk_localizacao;
        """))

        conn.execute(text("""
            CREATE OR REPLACE VIEW vw_fact_rendimento AS
            SELECT
                t.ano,
                m.cod_municipio, m.nome AS nome_municipio, m.uf, m.regiao,
                f.cod_escola,
                me.metrica, f.etapa, f.serie,
                f.valor, f.valor_num, f.valor_prop
            FROM fact_tx_rendimento f
            JOIN dim_tempo t      ON f.sk_tempo = t.sk_tempo
            JOIN dim_municipio m  ON f.cod_municipio = m.cod_municipio
            JOIN dim_metrica me   ON f.sk_metrica = me.sk_metrica;
        """))

        conn.execute(text("""
            CREATE OR REPLACE VIEW vw_fact_siope_receita AS
            SELECT
                t.ano,
                m.cod_municipio, m.nome AS nome_municipio, m.uf, m.regiao,
                tr.cod_receita, tr.descricao AS tipo_receita, tr.categoria AS categoria_receita,
                f.valor
            FROM fact_siope_receita f
            JOIN dim_tempo t         ON f.sk_tempo = t.sk_tempo
            JOIN dim_municipio m     ON f.cod_municipio = m.cod_municipio
            JOIN dim_tipo_receita tr ON f.sk_tipo_receita = tr.sk_tipo_receita;
        """))

        conn.execute(text("""
            CREATE OR REPLACE VIEW vw_fact_siope_despesa AS
            SELECT
                t.ano,
                m.cod_municipio, m.nome AS nome_municipio, m.uf, m.regiao,
                td.cod_despesa, td.descricao AS tipo_despesa, td.categoria AS categoria_despesa,
                f.valor
            FROM fact_siope_despesa f
            JOIN dim_tempo t         ON f.sk_tempo = t.sk_tempo
            JOIN dim_municipio m     ON f.cod_municipio = m.cod_municipio
            JOIN dim_tipo_despesa td ON f.sk_tipo_despesa = td.sk_tipo_despesa;
        """))

        conn.execute(text("""
            CREATE OR REPLACE VIEW vw_fact_siope_indicadores AS
            SELECT
                t.ano,
                m.cod_municipio, m.nome AS nome_municipio, m.uf, m.regiao,
                f.populacao, f.valor_pib, f.valor_pib_percapto
            FROM fact_siope_indicadores f
            JOIN dim_tempo t     ON f.sk_tempo = t.sk_tempo
            JOIN dim_municipio m ON f.cod_municipio = m.cod_municipio;
        """))

        # Views de compatibilidade com nomes CSV antigos
        conn.execute(text("""
            CREATE OR REPLACE VIEW vw_dados_normalizados_por_etapa AS
            SELECT ano, uf, cod_municipio, nome_municipio, dependencia AS tp_dependencia,
                   localizacao AS tp_localizacao, cod_escola, nome_escola,
                   grupo, etapa, qt
            FROM vw_fact_censo;
        """))

        conn.execute(text("""
            CREATE OR REPLACE VIEW vw_infra_escola_long AS
            SELECT ano, uf, cod_municipio, nome_municipio, dependencia AS tp_dependencia,
                   localizacao AS tp_localizacao, cod_escola, nome_escola,
                   grupo_infra AS "GrupoInfra", item AS "Item", possui AS "POSSUI"
            FROM vw_fact_infra;
        """))

        conn.execute(text("""
            CREATE OR REPLACE VIEW vw_dados_indigena_normalizado AS
            SELECT ano, uf, cod_municipio, nome_municipio, dependencia AS tp_dependencia,
                   localizacao AS tp_localizacao, cod_escola, nome_escola,
                   categoria AS "CategoriaIndigena", grupo, etapa, qt
            FROM vw_fact_indigena;
        """))

        conn.execute(text("""
            CREATE OR REPLACE VIEW vw_tx_rendimento_long AS
            SELECT t.ano, m.regiao AS "Região", m.uf, m.cod_municipio AS "Código do Município",
                   m.nome AS "Nome do Município", r.cod_escola AS "Código da Escola",
                   r.etapa AS "Etapa", r.serie AS "Serie",
                   me.metrica AS "Métrica", r.valor AS "Valor",
                   r.valor_num AS "Valor_num", r.valor_prop AS "Valor_prop"
            FROM fact_tx_rendimento r
            JOIN dim_tempo t    ON r.sk_tempo = t.sk_tempo
            JOIN dim_municipio m ON r.cod_municipio = m.cod_municipio
            JOIN dim_metrica me ON r.sk_metrica = me.sk_metrica;
        """))

        conn.execute(text("""
            CREATE OR REPLACE VIEW vw_siope_detalhado AS
            SELECT * FROM vw_fact_siope_receita;
        """))


# ═══════════════════════════════════════════════════════════════
# UPSERT DIMENSÕES: MUNICÍPIO E ESCOLA
# ═══════════════════════════════════════════════════════════════

def upsert_municipios_from_df(df: pd.DataFrame):
    if df is None or df.empty:
        return
    # aceita tanto colunas originais quanto nomes de view
    cols_map = {
        "CO_MUNICIPIO": "cod_municipio", "Código do Município": "cod_municipio",
        "NO_MUNICIPIO": "nome", "Nome do Município": "nome",
        "SG_UF": "uf", "UF": "uf",
    }
    src_cols = [c for c in cols_map if c in df.columns]
    if not src_cols:
        return

    # detecta quais colunas fonte existem
    has_cod = "CO_MUNICIPIO" in df.columns or "Código do Município" in df.columns
    has_nom = "NO_MUNICIPIO" in df.columns or "Nome do Município" in df.columns
    has_uf  = "SG_UF" in df.columns or "UF" in df.columns
    if not has_cod:
        return

    cod_col = "CO_MUNICIPIO" if "CO_MUNICIPIO" in df.columns else "Código do Município"
    nom_col = "NO_MUNICIPIO" if "NO_MUNICIPIO" in df.columns else ("Nome do Município" if "Nome do Município" in df.columns else None)
    uf_col  = "SG_UF" if "SG_UF" in df.columns else ("UF" if "UF" in df.columns else None)

    subset_cols = [cod_col]
    if nom_col: subset_cols.append(nom_col)
    if uf_col:  subset_cols.append(uf_col)

    dfu = df[subset_cols].drop_duplicates()
    rows = []
    for tup in dfu.itertuples(index=False):
        cod = _s(tup[0])
        if not cod:
            continue
        # Normaliza para str(int(float(...))) para alinhar com _muni_str() usado nas fact tables
        try:
            cod = str(int(float(cod)))
        except (ValueError, TypeError):
            pass
        nom = _s(tup[1]) if nom_col else None
        uf  = _s(tup[2]) if uf_col else None
        regiao = REGIOES.get(uf) if uf else None
        rows.append((cod, nom, uf, regiao))
    if not rows:
        return
    eng = get_engine()
    sql = (
        "INSERT INTO dim_municipio (cod_municipio, nome, uf, regiao) "
        "VALUES (:0, :1, :2, :3) "
        "ON CONFLICT (cod_municipio) DO UPDATE SET "
        "nome = EXCLUDED.nome, uf = EXCLUDED.uf, regiao = EXCLUDED.regiao"
    )
    with eng.begin() as conn:
        _exec_batch(conn, sql, rows)


def upsert_escolas_from_df(df: pd.DataFrame):
    """Upsert dim_escola. Se df tiver TP_DEPENDENCIA/TP_LOCALIZACAO, resolve sk_dependencia/sk_localizacao."""
    if df is None or df.empty:
        return
    # colunas fonte possíveis
    cod_col = next((c for c in ("CO_ENTIDADE", "Código da Escola") if c in df.columns), None)
    nom_col = next((c for c in ("NO_ENTIDADE", "Nome da Escola") if c in df.columns), None)
    muni_col = next((c for c in ("CO_MUNICIPIO", "Código do Município") if c in df.columns), None)
    dep_col = next((c for c in ("TP_DEPENDENCIA", "Dependência Administrativa") if c in df.columns), None)
    loc_col = next((c for c in ("TP_LOCALIZACAO", "Localização") if c in df.columns), None)

    if not cod_col:
        return

    dfu = df[[c for c in (cod_col, nom_col, muni_col, dep_col, loc_col) if c]].drop_duplicates()

    # resolve sk_dependencia e sk_localizacao se as colunas existirem
    dep_lookup = _resolve_dep_lookup() if dep_col else {}
    loc_lookup = _resolve_loc_lookup() if loc_col else {}

    rows = []
    for tup in dfu.itertuples(index=False):
        idx = 0
        ce = _s(tup[idx]); idx += 1
        if not ce:
            continue
        nm = _s(tup[idx]) if nom_col else None; idx += 1
        cm = _s(tup[idx]) if muni_col else None; idx += 1
        sk_dep = dep_lookup.get(_s(tup[idx]).upper().strip() if dep_col and pd.notna(tup[idx]) else "", None) if dep_col else None; idx += 1
        sk_loc = loc_lookup.get(_s(tup[idx]).upper().strip() if loc_col and pd.notna(tup[idx]) else "", None) if loc_col else None; idx += 1
        rows.append((ce, nm, cm, sk_dep, sk_loc))

    if not rows:
        return
    eng = get_engine()
    sql = (
        "INSERT INTO dim_escola (cod_escola, nome, cod_municipio, sk_dependencia, sk_localizacao) "
        "VALUES (:0, :1, :2, :3, :4) "
        "ON CONFLICT (cod_escola) DO UPDATE SET "
        "nome = EXCLUDED.nome, cod_municipio = EXCLUDED.cod_municipio, "
        "sk_dependencia = EXCLUDED.sk_dependencia, sk_localizacao = EXCLUDED.sk_localizacao"
    )
    with eng.begin() as conn:
        _exec_batch(conn, sql, rows)


# ═══════════════════════════════════════════════════════════════
# RESOLUÇÃO DE CHAVES SURROGADAS (em memória, com cache)
# ═══════════════════════════════════════════════════════════════

def _resolve_sk(lookup: dict, raw_value, fallback=None):
    if raw_value is None:
        return fallback
    key = str(raw_value).strip().upper()
    return lookup.get(key, fallback)


def _resolve_dep_lookup():
    eng = get_engine()
    with eng.connect() as conn:
        rows = conn.execute(text("SELECT cod_dependencia, sk_dependencia FROM dim_dependencia")).fetchall()
    return {r[0].upper().strip(): r[1] for r in rows}


def _resolve_loc_lookup():
    eng = get_engine()
    with eng.connect() as conn:
        rows = conn.execute(text("SELECT cod_localizacao, sk_localizacao FROM dim_localizacao")).fetchall()
    return {r[0].upper().strip(): r[1] for r in rows}


def _resolve_tempo(ano):
    eng = get_engine()
    with eng.connect() as conn:
        rows = conn.execute(text("SELECT ano, sk_tempo FROM dim_tempo")).fetchall()
    lookup = {r[0]: r[1] for r in rows}
    if ano in lookup:
        return lookup[ano]
    with eng.begin() as conn:
        r = conn.execute(text("INSERT INTO dim_tempo (ano) VALUES (:a) RETURNING sk_tempo"), {"a": int(ano)}).fetchone()
        return r[0]


def _resolve_grupo_medida(grupo, etapa):
    eng = get_engine()
    with eng.connect() as conn:
        rows = conn.execute(text("SELECT grupo, etapa, sk_grupo_medida FROM dim_grupo_medida")).fetchall()
    lookup = {(r[0], r[1]): r[2] for r in rows}
    key = (_s(grupo), _s(etapa))
    if key in lookup:
        return lookup[key]
    with eng.begin() as conn:
        r = conn.execute(
            text("INSERT INTO dim_grupo_medida (grupo, etapa) VALUES (:g, :e) RETURNING sk_grupo_medida"),
            {"g": _s(grupo), "e": _s(etapa)}
        ).fetchone()
        return r[0]


def _resolve_grupo_infra(grupo_infra):
    eng = get_engine()
    with eng.connect() as conn:
        rows = conn.execute(text("SELECT grupo_infra, sk_grupo_infra FROM dim_grupo_infra")).fetchall()
    lookup = {r[0].upper().strip(): r[1] for r in rows}
    key = _s(grupo_infra)
    if key and key.upper().strip() in lookup:
        return lookup[key.upper().strip()]
    with eng.begin() as conn:
        r = conn.execute(
            text("INSERT INTO dim_grupo_infra (grupo_infra) VALUES (:g) RETURNING sk_grupo_infra"),
            {"g": key}
        ).fetchone()
        return r[0]


def _resolve_categoria_indigena(categoria):
    eng = get_engine()
    with eng.connect() as conn:
        rows = conn.execute(text("SELECT categoria, sk_categoria_indigena FROM dim_categoria_indigena")).fetchall()
    lookup = {r[0].upper().strip(): r[1] for r in rows}
    key = _s(categoria)
    if key and key.upper().strip() in lookup:
        return lookup[key.upper().strip()]
    with eng.begin() as conn:
        r = conn.execute(
            text("INSERT INTO dim_categoria_indigena (categoria) VALUES (:c) RETURNING sk_categoria_indigena"),
            {"c": key}
        ).fetchone()
        return r[0]


def _resolve_metrica(metrica):
    eng = get_engine()
    with eng.connect() as conn:
        rows = conn.execute(text("SELECT metrica, sk_metrica FROM dim_metrica")).fetchall()
    lookup = {r[0].upper().strip(): r[1] for r in rows}
    key = _s(metrica)
    if key and key.upper().strip() in lookup:
        return lookup[key.upper().strip()]
    with eng.begin() as conn:
        r = conn.execute(
            text("INSERT INTO dim_metrica (metrica) VALUES (:m) RETURNING sk_metrica"),
            {"m": key}
        ).fetchone()
        return r[0]


def _resolve_tipo_receita(cod_receita):
    eng = get_engine()
    with eng.connect() as conn:
        rows = conn.execute(text("SELECT cod_receita, sk_tipo_receita FROM dim_tipo_receita")).fetchall()
    lookup = {r[0].upper().strip(): r[1] for r in rows}
    key = _s(cod_receita)
    if key and key.upper().strip() in lookup:
        return lookup[key.upper().strip()]
    with eng.begin() as conn:
        r = conn.execute(
            text("INSERT INTO dim_tipo_receita (cod_receita) VALUES (:c) RETURNING sk_tipo_receita"),
            {"c": key}
        ).fetchone()
        return r[0]


def _resolve_tipo_despesa(cod_despesa):
    eng = get_engine()
    with eng.connect() as conn:
        rows = conn.execute(text("SELECT cod_despesa, sk_tipo_despesa FROM dim_tipo_despesa")).fetchall()
    lookup = {r[0].upper().strip(): r[1] for r in rows}
    key = _s(cod_despesa)
    if key and key.upper().strip() in lookup:
        return lookup[key.upper().strip()]
    with eng.begin() as conn:
        r = conn.execute(
            text("INSERT INTO dim_tipo_despesa (cod_despesa) VALUES (:c) RETURNING sk_tipo_despesa"),
            {"c": key}
        ).fetchone()
        return r[0]


def load_all_lookups(anos=None):
    """Carrega todos os lookup tables em memória para resolução em lote.

    Se *anos* for informado, insere automaticamente os anos faltantes em
    ``dim_tempo`` antes de ler o lookup.
    """
    eng = get_engine()
    lookups = {}
    with eng.begin() as conn:
        for table, key_col, val_col in [
            ("dim_grupo_infra", "grupo_infra", "sk_grupo_infra"),
            ("dim_categoria_indigena", "categoria", "sk_categoria_indigena"),
            ("dim_metrica", "metrica", "sk_metrica"),
            ("dim_tipo_receita", "cod_receita", "sk_tipo_receita"),
            ("dim_tipo_despesa", "cod_despesa", "sk_tipo_despesa"),
        ]:
            rows = conn.execute(text(f"SELECT {key_col}, {val_col} FROM {table}")).fetchall()
            lookups[table] = {r[0].upper().strip(): r[1] for r in rows}

        # dim_grupo_medida: chaves compostas (grupo, etapa)
        rows = conn.execute(text("SELECT grupo, etapa, sk_grupo_medida FROM dim_grupo_medida")).fetchall()
        lookups["dim_grupo_medida"] = {(r[0], r[1]): r[2] for r in rows}

        # dim_tempo: garante que todos os anos necessários existam
        if anos:
            for ano in sorted(set(a for a in anos if a is not None)):
                conn.execute(text(
                    "INSERT INTO dim_tempo (ano) VALUES (:a) ON CONFLICT (ano) DO NOTHING"
                ), {"a": int(ano)})
        rows = conn.execute(text("SELECT ano, sk_tempo FROM dim_tempo")).fetchall()
        lookups["dim_tempo"] = {r[0]: r[1] for r in rows}

        # dim_dependencia (por cod_dependencia)
        rows = conn.execute(text("SELECT cod_dependencia, sk_dependencia FROM dim_dependencia")).fetchall()
        lookups["dim_dependencia"] = {r[0].upper().strip(): r[1] for r in rows}

        # dim_localizacao (por cod_localizacao)
        rows = conn.execute(text("SELECT cod_localizacao, sk_localizacao FROM dim_localizacao")).fetchall()
        lookups["dim_localizacao"] = {r[0].upper().strip(): r[1] for r in rows}

    return lookups


def _resolve_sk_bulk(lookup: dict, raw_value, fallback=None):
    if raw_value is None:
        return fallback
    key = str(raw_value).strip().upper()
    return lookup.get(key, fallback)


# ═══════════════════════════════════════════════════════════════
# INSERÇÃO DE FATOS
# ═══════════════════════════════════════════════════════════════

def insert_censo_medidas(df_long: pd.DataFrame):
    if df_long is None or df_long.empty:
        return
    req = ["NU_ANO_CENSO", "CO_ENTIDADE", "Grupo", "Etapa", "QT"]
    miss = [c for c in req if c not in df_long.columns]
    if miss:
        return

    anos = [_i(x) for x in df_long["NU_ANO_CENSO"] if _i(x) is not None]
    lookups = load_all_lookups(anos=anos)
    tempo_lookup = lookups["dim_tempo"]
    gm_lookup = lookups["dim_grupo_medida"]

    rows = []
    for _, row in df_long.iterrows():
        ano = _i(row.get("NU_ANO_CENSO"))
        cod_escola = _s(row.get("CO_ENTIDADE"))
        grupo = _s(row.get("Grupo"))
        etapa = _s(row.get("Etapa"))
        qt = _i(row.get("QT"))
        if not all([ano, cod_escola, grupo, etapa, qt is not None]):
            continue

        sk_tempo = tempo_lookup.get(ano)
        if sk_tempo is None:
            continue
        sk_gm = gm_lookup.get((grupo, etapa))
        if sk_gm is None:
            continue

        rows.append((sk_tempo, cod_escola, sk_gm, qt))

    if not rows:
        return
    eng = get_engine()
    sql = (
        "INSERT INTO fact_censo_medida (sk_tempo, cod_escola, sk_grupo_medida, qt) "
        "VALUES (:0, :1, :2, :3) "
        "ON CONFLICT (sk_tempo, cod_escola, sk_grupo_medida) DO UPDATE SET qt = EXCLUDED.qt"
    )
    with eng.begin() as conn:
        _exec_batch(conn, sql, rows)


def insert_infra_escola(df_long: pd.DataFrame):
    if df_long is None or df_long.empty:
        return
    req = ["NU_ANO_CENSO", "CO_ENTIDADE", "GrupoInfra", "Item", "POSSUI"]
    miss = [c for c in req if c not in df_long.columns]
    if miss:
        return

    anos = [_i(x) for x in df_long["NU_ANO_CENSO"] if _i(x) is not None]
    lookups = load_all_lookups(anos=anos)
    tempo_lookup = lookups["dim_tempo"]
    gi_lookup = lookups["dim_grupo_infra"]

    rows = []
    for _, row in df_long.iterrows():
        ano = _i(row.get("NU_ANO_CENSO"))
        cod_escola = _s(row.get("CO_ENTIDADE"))
        grupo_infra = _s(row.get("GrupoInfra"))
        item = _s(row.get("Item"))
        possui = _i(row.get("POSSUI"))
        if not all([ano, cod_escola, grupo_infra, item, possui is not None]):
            continue

        sk_tempo = tempo_lookup.get(ano)
        if sk_tempo is None:
            continue
        sk_gi = gi_lookup.get(grupo_infra.upper().strip() if grupo_infra else "")
        if sk_gi is None:
            continue

        rows.append((sk_tempo, cod_escola, sk_gi, item, int(possui)))

    if not rows:
        return
    eng = get_engine()
    sql = (
        "INSERT INTO fact_infra_escola (sk_tempo, cod_escola, sk_grupo_infra, item, possui) "
        "VALUES (:0, :1, :2, :3, :4) "
        "ON CONFLICT (sk_tempo, cod_escola, item) DO UPDATE SET "
        "sk_grupo_infra = EXCLUDED.sk_grupo_infra, possui = EXCLUDED.possui"
    )
    with eng.begin() as conn:
        _exec_batch(conn, sql, rows)


def insert_indigena(df_long: pd.DataFrame):
    if df_long is None or df_long.empty:
        return
    req = ["NU_ANO_CENSO", "CO_ENTIDADE", "CategoriaIndigena", "Grupo", "Etapa", "QT"]
    miss = [c for c in req if c not in df_long.columns]
    if miss:
        return

    anos = [_i(x) for x in df_long["NU_ANO_CENSO"] if _i(x) is not None]
    lookups = load_all_lookups(anos=anos)
    tempo_lookup = lookups["dim_tempo"]
    gm_lookup = lookups["dim_grupo_medida"]
    ci_lookup = lookups["dim_categoria_indigena"]

    rows = []
    for _, row in df_long.iterrows():
        ano = _i(row.get("NU_ANO_CENSO"))
        cod_escola = _s(row.get("CO_ENTIDADE"))
        categoria = _s(row.get("CategoriaIndigena"))
        grupo = _s(row.get("Grupo"))
        etapa = _s(row.get("Etapa"))
        qt = _i(row.get("QT"))
        if not all([ano, cod_escola, categoria, grupo, etapa, qt is not None]):
            continue

        sk_tempo = tempo_lookup.get(ano)
        if sk_tempo is None:
            continue
        sk_ci = ci_lookup.get(categoria.upper().strip() if categoria else "")
        if sk_ci is None:
            continue
        sk_gm = gm_lookup.get((grupo, etapa))
        if sk_gm is None:
            continue

        rows.append((sk_tempo, cod_escola, sk_ci, sk_gm, qt))

    if not rows:
        return
    eng = get_engine()
    sql = (
        "INSERT INTO fact_indigena (sk_tempo, cod_escola, sk_categoria_indigena, sk_grupo_medida, qt) "
        "VALUES (:0, :1, :2, :3, :4) "
        "ON CONFLICT (sk_tempo, cod_escola, sk_categoria_indigena, sk_grupo_medida) DO UPDATE SET qt = EXCLUDED.qt"
    )
    with eng.begin() as conn:
        _exec_batch(conn, sql, rows)


def insert_tx_rendimento(df_long: pd.DataFrame):
    if df_long is None or df_long.empty:
        return

    anos = [_i(x) for x in df_long["Ano"] if _i(x) is not None]
    lookups = load_all_lookups(anos=anos)
    tempo_lookup = lookups["dim_tempo"]
    met_lookup = lookups["dim_metrica"]

    cols = {
        "ano": "Ano",
        "metrica": "Métrica",
        "etapa": "Etapa",
        "serie": "Serie",
        "valor": "Valor",
        "valor_num": "Valor_num",
        "valor_prop": "Valor_prop",
    }
    cod_col = "Código da Escola"
    muni_col = next((c for c in ("Código do Município",) if c in df_long.columns), None)

    rows = []
    for _, row in df_long.iterrows():
        ano = _i(row.get(cols["ano"]))
        cod_muni = _s(row.get(muni_col)) if muni_col else None
        if cod_muni:
            try:
                cod_muni = str(int(float(cod_muni)))
            except (ValueError, TypeError):
                pass
        cod_escola = _s(row.get(cod_col)) if cod_col in df_long.columns else None
        if not cod_escola:
            cod_escola = ""
        metrica = _s(row.get(cols["metrica"]))
        etapa = _s(row.get(cols["etapa"]))
        serie = _i(row.get(cols["serie"]))
        if serie is None:
            serie = 0
        valor = _s(row.get(cols["valor"]))
        valor_num = _to_float_or_none(row.get(cols["valor_num"]))
        valor_prop = _to_float_or_none(row.get(cols["valor_prop"]))

        if not all([ano, metrica]):
            continue
        sk_tempo = tempo_lookup.get(ano)
        if sk_tempo is None:
            continue
        sk_met = met_lookup.get(metrica.upper().strip() if metrica else "")
        if sk_met is None:
            continue

        rows.append((sk_tempo, cod_muni, cod_escola, sk_met, etapa, serie, valor, valor_num, valor_prop))

    if not rows:
        return
    eng = get_engine()
    sql = (
        "INSERT INTO fact_tx_rendimento (sk_tempo, cod_municipio, cod_escola, sk_metrica, etapa, serie, valor, valor_num, valor_prop) "
        "VALUES (:0, :1, :2, :3, :4, :5, :6, :7, :8) "
        "ON CONFLICT (sk_tempo, cod_municipio, cod_escola, sk_metrica, etapa, serie) DO UPDATE SET "
        "valor = EXCLUDED.valor, valor_num = EXCLUDED.valor_num, valor_prop = EXCLUDED.valor_prop"
    )
    with eng.begin() as conn:
        _exec_batch(conn, sql, rows)


# ═══════════════════════════════════════════════════════════════
# SIOPE: JSONB → FATOS ESTRUTURADOS
# ═══════════════════════════════════════════════════════════════

def insert_siope_raw(df: pd.DataFrame):
    """Insere SIOPE JSONB bruto (mantido para retrocompatibilidade)."""
    if df is None or df.empty:
        return
    has = {c: c in df.columns for c in ["NUM_ANO", "NUM_PERI", "SIG_UF", "COD_MUNI", "PERIODO_LABEL"]}

    def _muni_str(v):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        try:
            return str(int(float(v)))
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


def insert_siope_receita(df: pd.DataFrame):
    """Extrai receitas do DataFrame SIOPE → fact_siope_receita."""
    if df is None or df.empty:
        return

    anos = [_i(x) for x in df["NUM_ANO"] if _i(x) is not None]
    lookups = load_all_lookups(anos=anos)
    tempo_lookup = lookups["dim_tempo"]
    rec_lookup = lookups["dim_tipo_receita"]

    def _muni_str(v):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        try:
            return str(int(float(v)))
        except Exception:
            return str(v) if str(v).strip() else None

    def _num(v):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        try:
            return float(v)
        except Exception:
            return None

    ano_col = next((c for c in ("NUM_ANO",) if c in df.columns), None)
    muni_col = next((c for c in ("COD_MUNI",) if c in df.columns), None)
    if not ano_col or not muni_col:
        return

    rows = []
    for _, row in df.iterrows():
        ano = _i(row.get(ano_col))
        if ano is None:
            continue
        sk_tempo = tempo_lookup.get(ano)
        if sk_tempo is None:
            continue
        cod_muni = _muni_str(row.get(muni_col))
        if not cod_muni:
            continue

        for json_key, cod_receita in SIOPE_RECEITA_KEYS.items():
            val = _num(row.get(json_key))
            if val is None:
                continue
            sk = rec_lookup.get(cod_receita)
            if sk is None:
                continue
            rows.append((sk_tempo, cod_muni, sk, val))

    if not rows:
        return
    eng = get_engine()
    sql = (
        "INSERT INTO fact_siope_receita (sk_tempo, cod_municipio, sk_tipo_receita, valor) "
        "VALUES (:0, :1, :2, :3) "
        "ON CONFLICT (sk_tempo, cod_municipio, sk_tipo_receita) DO UPDATE SET valor = EXCLUDED.valor"
    )
    with eng.begin() as conn:
        _exec_batch(conn, sql, rows)


def insert_siope_despesa(df: pd.DataFrame):
    """Extrai despesas do DataFrame SIOPE → fact_siope_despesa."""
    if df is None or df.empty:
        return

    anos = [_i(x) for x in df["NUM_ANO"] if _i(x) is not None]
    lookups = load_all_lookups(anos=anos)
    tempo_lookup = lookups["dim_tempo"]
    desp_lookup = lookups["dim_tipo_despesa"]

    def _muni_str(v):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        try:
            return str(int(float(v)))
        except Exception:
            return str(v) if str(v).strip() else None

    def _num(v):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        try:
            return float(v)
        except Exception:
            return None

    ano_col = next((c for c in ("NUM_ANO",) if c in df.columns), None)
    muni_col = next((c for c in ("COD_MUNI",) if c in df.columns), None)
    if not ano_col or not muni_col:
        return

    rows = []
    for _, row in df.iterrows():
        ano = _i(row.get(ano_col))
        if ano is None:
            continue
        sk_tempo = tempo_lookup.get(ano)
        if sk_tempo is None:
            continue
        cod_muni = _muni_str(row.get(muni_col))
        if not cod_muni:
            continue

        for json_key, cod_despesa in SIOPE_DESPESA_KEYS.items():
            val = _num(row.get(json_key))
            if val is None:
                continue
            sk = desp_lookup.get(cod_despesa)
            if sk is None:
                continue
            rows.append((sk_tempo, cod_muni, sk, val))

    if not rows:
        return
    eng = get_engine()
    sql = (
        "INSERT INTO fact_siope_despesa (sk_tempo, cod_municipio, sk_tipo_despesa, valor) "
        "VALUES (:0, :1, :2, :3) "
        "ON CONFLICT (sk_tempo, cod_municipio, sk_tipo_despesa) DO UPDATE SET valor = EXCLUDED.valor"
    )
    with eng.begin() as conn:
        _exec_batch(conn, sql, rows)


def insert_siope_indicadores(df: pd.DataFrame):
    """Extrai indicadores demográficos/financeiros → fact_siope_indicadores."""
    if df is None or df.empty:
        return

    anos = [_i(x) for x in df["NUM_ANO"] if _i(x) is not None]
    lookups = load_all_lookups(anos=anos)
    tempo_lookup = lookups["dim_tempo"]

    def _muni_str(v):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        try:
            return str(int(float(v)))
        except Exception:
            return str(v) if str(v).strip() else None

    def _num(v):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        try:
            return float(v)
        except Exception:
            return None

    ano_col = next((c for c in ("NUM_ANO",) if c in df.columns), None)
    muni_col = next((c for c in ("COD_MUNI",) if c in df.columns), None)
    if not ano_col or not muni_col:
        return

    IND_FIELDS = {
        "NUM_POPU": "populacao",
        "VAL_PIB": "valor_pib",
        "VAL_PIB_PERCAPTO": "valor_pib_percapto",
    }

    rows = []
    for _, row in df.iterrows():
        ano = _i(row.get(ano_col))
        if ano is None:
            continue
        sk_tempo = tempo_lookup.get(ano)
        if sk_tempo is None:
            continue
        cod_muni = _muni_str(row.get(muni_col))
        if not cod_muni:
            continue

        populacao = _num(row.get("NUM_POPU"))
        pib = _num(row.get("VAL_PIB"))
        pib_perc = _num(row.get("VAL_PIB_PERCAPTO"))

        if populacao is None and pib is None and pib_perc is None:
            continue

        rows.append((sk_tempo, cod_muni, populacao, pib, pib_perc))

    if not rows:
        return
    eng = get_engine()
    sql = (
        "INSERT INTO fact_siope_indicadores (sk_tempo, cod_municipio, populacao, valor_pib, valor_pib_percapto) "
        "VALUES (:0, :1, :2, :3, :4) "
        "ON CONFLICT (sk_tempo, cod_municipio) DO UPDATE SET "
        "populacao = EXCLUDED.populacao, valor_pib = EXCLUDED.valor_pib, valor_pib_percapto = EXCLUDED.valor_pib_percapto"
    )
    with eng.begin() as conn:
        _exec_batch(conn, sql, rows)
