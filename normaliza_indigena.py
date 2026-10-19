# normaliza_indigena.py
# -*- coding: utf-8 -*-
"""
Recortes indígenas do Censo Escolar:
- Lê todos os CSVs em data/microDados (gerados pelo coleta_censo.py).
- Aplica dicionário de tipos e filtra pela UF alvo.
- Detecta campos indígenas (nomes variam por ano).
- Gera dataset em formato longo com:
    • Contagem de escolas no recorte (Escola Indígena / Em Terra Indígena / Com Língua Indígena)
    • Matrículas Indígenas (TOTAL e por ETAPA) — a soma por etapa SEMPRE fecha no total
    • Docentes (total) e por etapa (reais ou estimados)
- (Opcional) “Matrículas” gerais por etapa podem ser incluídas com flag (default: False)
- Salva em OUT/dados_indigena_normalizado.csv
"""

import glob
from pathlib import Path
import re
import numpy as np
import pandas as pd

from config import (
    MICRODADOS_DIR, DICIONARIO_PATH,
    ARQUIVO_SAIDA_BRUTO, ARQUIVO_INDIGENA,
    UF_TARGET, LIMITE_COLS,
    USAR_DOCENTES_POR_ETAPA_SE_EXISTIR, ESTIMAR_DOCENTES_POR_ETAPA,
    ID_VARS_CANDIDATAS,
)

# ===== feature flags com defaults seguros (podem ser definidos no config.py) =====
try:
    from config import ESTIMAR_MAT_INDIGENA_POR_ETAPA  # True/False
except Exception:
    ESTIMAR_MAT_INDIGENA_POR_ETAPA = True

try:
    from config import INCLUIR_MATRICULAS_GERAIS_NO_INDIGENA  # True/False
except Exception:
    INCLUIR_MATRICULAS_GERAIS_NO_INDIGENA = False


# ==========================
# Funções auxiliares
# ==========================

def carregar_dicionario_tipos(path_excel: Path, limite: int = LIMITE_COLS):
    df_raw = pd.read_excel(path_excel, sheet_name="microdados_unidade_coleta", header=None)

    nomes = (
        df_raw.iloc[9:, 1]
        .dropna()
        .astype(str)
        .str.strip()
        .tolist()[:limite]
    )

    tipos = (
        df_raw.iloc[9:, [1, 3]]
        .dropna()
        .astype({1: str, 3: str})
    )
    tipos.columns = ['variavel', 'tipo']
    mapa_tipos = {'Char': 'string', 'Num': 'Int64'}
    dict_tipos = {
        row['variavel'].strip(): mapa_tipos.get(row['tipo'].strip(), 'string')
        for _, row in tipos.iterrows()
    }
    return nomes, dict_tipos


def ler_csv_padrao(caminho: Path, dtype_map: dict, nomes_ref: list) -> pd.DataFrame:
    # tenta ISO-8859-1 → UTF-8
    try:
        df = pd.read_csv(
            caminho, encoding='ISO-8859-1', sep=';', header=0,
            na_values=[".", "", "NA", "NaN"], dtype=str, low_memory=False
        )
    except UnicodeDecodeError:
        df = pd.read_csv(
            caminho, encoding='utf-8', sep=';', header=0,
            na_values=[".", "", "NA", "NaN"], dtype=str, low_memory=False
        )

    df.columns = [str(c).upper().strip() for c in df.columns]

    # caso raro: sem header (0,1,2,...)
    if all(col.isdigit() for col in df.columns):
        if df.shape[1] >= len(nomes_ref):
            df = df.iloc[:, :len(nomes_ref)]
            df.columns = [c.upper().strip() for c in nomes_ref]

    # aplica tipos somente no que existir
    for col, t in dtype_map.items():
        col_up = col.upper().strip()
        if col_up in df.columns:
            if t == 'Int64':
                df[col_up] = (
                    pd.to_numeric(
                        pd.Series(df[col_up], dtype="string")
                        .str.replace(".", "", regex=False)   # milhar
                        .str.replace(",", ".", regex=False)  # decimal BR
                        .str.strip(),
                        errors="coerce"
                    ).astype("Int64")
                )
            else:
                df[col_up] = pd.Series(df[col_up], dtype="string")
    return df


def to_int_series(serie) -> pd.Series:
    return (
        pd.to_numeric(
            pd.Series(serie, dtype="string")
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
            .str.strip(),
            errors="coerce"
        ).fillna(0).astype("Int64")
    )


def ensure_unique_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    df = df.copy()
    df.columns = df.columns.map(str)
    return df.loc[:, ~df.columns.duplicated()]


def expandir_grupo(df: pd.DataFrame, mapeamento: dict, nome_grupo: str,
                   nome_valor: str = "QT", filtro_mask: pd.Series | None = None,
                   categoria_indigena: str = "") -> pd.DataFrame:
    linhas = []
    base_df = df if filtro_mask is None else df.loc[filtro_mask].copy()
    if base_df.empty:
        cols_base = list(df.columns) if isinstance(df, pd.DataFrame) else []
        return pd.DataFrame(columns=cols_base + ["Grupo", "Etapa", nome_valor, "CategoriaIndigena"])

    for etapa, coluna in mapeamento.items():
        col_up = coluna.upper().strip()
        if col_up in base_df.columns:
            serie = base_df[col_up]
            if not pd.api.types.is_integer_dtype(serie):
                serie = to_int_series(serie)
            mask_val = serie.fillna(0).ne(0)
            if mask_val.any():
                bloco = base_df.loc[mask_val].copy()
                bloco["Grupo"] = nome_grupo
                bloco["Etapa"] = etapa
                bloco[nome_valor] = serie[mask_val].astype("Int64")
                bloco["CategoriaIndigena"] = categoria_indigena
                linhas.append(bloco)

    if not linhas:
        cols_base = list(df.columns) if isinstance(df, pd.DataFrame) else []
        return pd.DataFrame(columns=cols_base + ["Grupo", "Etapa", nome_valor, "CategoriaIndigena"])
    return pd.concat(linhas, ignore_index=True)


# ===== detecção de matrículas indígenas =====
def _col_total_mat_indigena(df_cols: list[str]) -> str | None:
    candidatos = [
        "QT_MAT_BAS_INDIGENA", "QT_MAT_INDIGENA", "QT_MAT_TOT_INDIGENA",
        "QT_MAT_BAS_INDIG", "QT_MAT_INDIG",
    ]
    up = {c.upper().strip() for c in df_cols}
    for c in candidatos:
        if c in up:
            return c
    return None


_ETAPAS_TOKENS = {
    "Educação Especial":        ["ESP"],
    "Ed. Infantil - Creche":    ["INF_CRE", "INFANTIL_CRECHE"],
    "Ed. Infantil - Pré-Escola":["INF_PRE", "INFANTIL_PRE"],
    "Ensino Fund. - Anos Iniciais": ["FUND_AI", "FUNDAMENTAL_AI"],
    "Ensino Fund. - Anos Finais":   ["FUND_AF", "FUNDAMENTAL_AF"],
    "Ensino Médio":             ["MED", "ENSINO_MEDIO"],
    "EJA - Ensino Fundamental": ["EJA_FUND"],
    "EJA - Ensino Médio":       ["EJA_MED"],
    # opcionais INT:
    "Ed. Infantil - Creche - Tempo Integral": ["INF_CRE_INT"],
    "Ed. Infantil - Pré-Escola - Tempo Integral": ["INF_PRE_INT"],
    "Ensino Fund. - Anos Iniciais - Tempo Integral": ["FUND_AI_INT"],
    "Ensino Fund. - Anos Finais - Tempo Integral":   ["FUND_AF_INT"],
    "Ensino Médio - Tempo Integral": ["MED_INT"],
}

def _mapear_matriculas_indigenas_por_etapa(df_cols: list[str]) -> dict:
    up = [c.upper().strip() for c in df_cols]
    result = {}
    for etapa, tokens in _ETAPAS_TOKENS.items():
        patt = re.compile(r"QT[_]?MAT.*(" + "|".join(map(re.escape, tokens)) + r").*(INDIG|INDIGENA)")
        hit = next((c for c in up if patt.search(c)), None)
        if hit:
            result[etapa] = hit
    return result


# ==========================
# Pipeline principal
# ==========================

def normalizar_indigena():
    print("🔍 Carregando dicionário...")
    nomes_colunas, tipos_colunas = carregar_dicionario_tipos(DICIONARIO_PATH, LIMITE_COLS)

    arquivos_csv = glob.glob(str(MICRODADOS_DIR / '*.csv'))
    if not arquivos_csv:
        raise FileNotFoundError(f"Nenhum CSV encontrado em {MICRODADOS_DIR}")

    dfs = []
    for caminho in sorted(arquivos_csv):
        p = Path(caminho)
        print(f"📥 Lendo {p.name}...")
        try:
            df = ler_csv_padrao(p, tipos_colunas, nomes_colunas)

            # força NU_ANO_CENSO a partir do nome do arquivo, quando possível
            if 'NU_ANO_CENSO' in df.columns:
                ano = ''.join(filter(str.isdigit, p.stem))
                if ano.isdigit():
                    df['NU_ANO_CENSO'] = int(ano)

            # filtra por UF
            if 'SG_UF' in df.columns and UF_TARGET:
                df = df[df['SG_UF'] == UF_TARGET]

            dfs.append(df)
        except Exception as e:
            print(f"❌ Erro em {p.name}: {e}")

    if not dfs:
        raise RuntimeError("Nenhum DataFrame foi carregado com sucesso.")

    df_final = pd.concat(dfs, ignore_index=True)
    df_final.to_csv(ARQUIVO_SAIDA_BRUTO, index=False, encoding='ISO-8859-1')
    print(f"✅ Arquivo bruto filtrado salvo: {ARQUIVO_SAIDA_BRUTO} | Linhas: {len(df_final):,}")

    # ---- DETECÇÃO FLEXÍVEL (flags) ----
    cols_upper = set(df_final.columns)

    flag_escola_candidates = ["IN_EDUCACAO_INDIGENA", "IN_INDIGENA", "TP_ESCOLA_INDIGENA", "IN_COMUNIDADE_INDIGENA"]
    presentes_flags = [c for c in flag_escola_candidates if c in cols_upper]

    def _bin_flag(s):
        v = pd.Series(s, dtype="string").str.strip().str.upper()
        return v.isin(["1", "SIM", "S", "TRUE", "T", "X"])

    mask_escola_indigena = pd.Series(False, index=df_final.index)
    for c in presentes_flags:
        mask_escola_indigena |= _bin_flag(df_final[c])

    # fallback via colunas de matrícula indígena
    mat_indig_cols = [c for c in df_final.columns if ("INDIG" in c and "MAT" in c)]
    if mat_indig_cols:
        somas = pd.DataFrame({c: to_int_series(df_final[c]) if c in df_final.columns else 0 for c in mat_indig_cols})
        any_pos = (somas.fillna(0) > 0).any(axis=1)
        mask_escola_indigena |= any_pos

    terra_candidates = ["TP_LOCALIZACAO_DIFERENCIADA", "TP_LOC_DIF", "IN_TERRITORIO_INDIGENA", "TP_TERRITORIO_INDIGENA"]
    col_terra = next((c for c in terra_candidates if c in cols_upper), None)
    mask_terra_indigena = pd.Series(False, index=df_final.index)
    if col_terra:
        v = pd.Series(df_final[col_terra], dtype="string").str.strip().str.upper()
        mask_terra_indigena = v.isin(["1", "TERRA INDÍGENA", "TERRA INDIGENA", "SIM", "S", "TRUE", "T"])

    lingua_candidates = ["IN_LINGUA_INDIGENA", "TP_LINGUA_INDIGENA", "IN_OFERTA_LINGUA_INDIGENA"]
    col_lingua = next((c for c in lingua_candidates if c in cols_upper), None)
    mask_lingua_indigena = pd.Series(False, index=df_final.index)
    if col_lingua:
        mask_lingua_indigena = _bin_flag(df_final[col_lingua])

    # prioridade de categoria
    categoria = np.where(mask_escola_indigena, "Escola Indígena",
                 np.where(mask_terra_indigena,  "Em Terra Indígena",
                 np.where(mask_lingua_indigena, "Com Língua Indígena", "Não indígena")))
    df_final["CategoriaIndigena"] = pd.Series(categoria, index=df_final.index)

    # ---- mapeamentos gerais (para docentes e para estimar distribuição, se precisar) ----
    etapas_matriculas_gerais = {
        "Educação Especial": "QT_MAT_ESP",
        "Ed. Infantil - Creche": "QT_MAT_INF_CRE",
        "Ed. Infantil - Pré-Escola": "QT_MAT_INF_PRE",
        "Ensino Fund. - Anos Iniciais": "QT_MAT_FUND_AI",
        "Ensino Fund. - Anos Finais": "QT_MAT_FUND_AF",
        "Ensino Médio": "QT_MAT_MED",
        "EJA - Ensino Fundamental": "QT_MAT_EJA_FUND",
        "EJA - Ensino Médio": "QT_MAT_EJA_MED",
        # versões INT das etapas, se quiser incluir no rateio, adicione aqui
    }

    docentes_geral = {"Educação Básica (Total)": "QT_DOC_BAS"}
    etapas_docentes_reais = {
        "Educação Especial": "QT_DOC_ESP",
        "Ed. Infantil - Creche": "QT_DOC_INF_CRE",
        "Ed. Infantil - Pré-Escola": "QT_DOC_INF_PRE",
        "Ensino Fund. - Anos Iniciais": "QT_DOC_FUND_AI",
        "Ensino Fund. - Anos Finais": "QT_DOC_FUND_AF",
        "Ensino Médio": "QT_DOC_MED",
        "EJA - Ensino Fundamental": "QT_DOC_EJA_FUND",
        "EJA - Ensino Médio": "QT_DOC_EJA_MED",
    }

    # ---- matrículas indígenas: total e por etapa ----
    col_total_indig = _col_total_mat_indigena(df_final.columns.tolist())
    etapas_matriculas_indig = _mapear_matriculas_indigenas_por_etapa(df_final.columns.tolist())

    id_vars = [c for c in ID_VARS_CANDIDATAS if c in df_final.columns]

    def selecionar_cols(df_long: pd.DataFrame) -> pd.DataFrame:
        cols = id_vars + ["CategoriaIndigena", "Grupo", "Etapa", "QT"]
        out = df_long.loc[:, [c for c in cols if c in df_long.columns]]
        return ensure_unique_columns(out)

    # máscaras categoria
    mask_cat_escola = df_final["CategoriaIndigena"].eq("Escola Indígena")
    mask_cat_terra  = df_final["CategoriaIndigena"].eq("Em Terra Indígena")
    mask_cat_lingua = df_final["CategoriaIndigena"].eq("Com Língua Indígena")

    # --- contagem de escolas
    def contar_escolas(mask, categoria_nome: str) -> pd.DataFrame:
        base = df_final.loc[mask, id_vars + ["CO_ENTIDADE"]].dropna(subset=["CO_ENTIDADE"]).copy()
        if base.empty:
            return pd.DataFrame(columns=id_vars + ["CategoriaIndigena", "Grupo", "Etapa", "QT"])
        base = base.drop_duplicates(subset=["CO_ENTIDADE"])
        base["CategoriaIndigena"] = categoria_nome
        base["Grupo"] = "Escolas"
        base["Etapa"] = "Todas"
        base["QT"] = 1
        return base

    esc_escola = contar_escolas(mask_cat_escola, "Escola Indígena")
    esc_terra  = contar_escolas(mask_cat_terra,  "Em Terra Indígena")
    esc_lingua = contar_escolas(mask_cat_lingua, "Com Língua Indígena")

    # --- helper: distribuição exata por etapa para fechar no total (maior resto)
    def distribuir_total_por_etapa(row, total_col: str, etapas_map: dict) -> list[tuple[str, int]]:
        total = int(row[total_col])
        if total <= 0:
            return []

        # pesos das etapas a partir das matrículas GERAIS (quando não temos colunas indígenas por etapa)
        etapas_presentes, pesos = [], []
        for etapa, col in etapas_map.items():
            if col in row.index:
                v = int(to_int_series([row[col]])[0])
                if v > 0:
                    etapas_presentes.append(etapa)
                    pesos.append(v)

        if not pesos:
            # se não houver nenhuma etapa geral >0, joga tudo em "Não detalhado"
            return [("Não detalhado", total)]

        pesos = np.array(pesos, dtype=float)
        frac = pesos / pesos.sum()
        base = np.floor(frac * total).astype(int)
        restante = total - base.sum()

        # maior resto
        restos = frac * total - base
        ordem = np.argsort(-restos)
        for k in ordem[:restante]:
            base[k] += 1

        return list(zip(etapas_presentes, base.tolist()))

    # --- MATRÍCULAS INDÍGENAS (TOTAL)
    def mat_indigena_total(mask, categoria_nome: str) -> pd.DataFrame:
        if not col_total_indig or col_total_indig not in df_final.columns:
            return pd.DataFrame(columns=id_vars + ["CategoriaIndigena", "Grupo", "Etapa", "QT"])
        base = df_final.loc[mask, id_vars + [col_total_indig]].copy()
        base[col_total_indig] = to_int_series(base[col_total_indig])
        base = base[base[col_total_indig].fillna(0).ne(0)]
        if base.empty:
            return pd.DataFrame(columns=id_vars + ["CategoriaIndigena", "Grupo", "Etapa", "QT"])
        base["CategoriaIndigena"] = categoria_nome
        base["Grupo"] = "Matrículas Indígenas (Total)"
        base["Etapa"] = "Todas"
        base["QT"] = base[col_total_indig].astype("Int64")
        return base.drop(columns=[col_total_indig])

    # --- MATRÍCULAS INDÍGENAS (ETAPAS) -> usa colunas indígenas se existirem; senão, ESTIMA do total
    def mat_indigena_etapas(mask, categoria_nome: str) -> pd.DataFrame:
        base = df_final.loc[mask].copy()
        linhas = []

        # caso 1: existem colunas indígenas por etapa → usar diretamente
        if etapas_matriculas_indig:
            exp = expandir_grupo(
                base, etapas_matriculas_indig,
                "Matrículas Indígenas (Etapas)", "QT",
                filtro_mask=None, categoria_indigena=categoria_nome
            )
            return exp

        # caso 2: NÃO existem colunas indígenas por etapa, mas temos o total → estimar
        if ESTIMAR_MAT_INDIGENA_POR_ETAPA and col_total_indig and col_total_indig in base.columns:
            # garantir numérico no total
            base[col_total_indig] = to_int_series(base[col_total_indig])

            # vamos precisar das colunas gerais para os pesos
            for col in set(etapas_matriculas_gerais.values()):
                if col not in base.columns:
                    base[col] = 0
                else:
                    base[col] = to_int_series(base[col])

            for _, row in base.iterrows():
                tot = int(row[col_total_indig])
                if tot <= 0:
                    continue
                partes = distribuir_total_por_etapa(row, col_total_indig, etapas_matriculas_gerais)
                for etapa, qtd in partes:
                    nova = {k: row.get(k) for k in id_vars}
                    nova["CategoriaIndigena"] = categoria_nome
                    nova["Grupo"] = "Matrículas Indígenas (Etapas)"
                    nova["Etapa"] = etapa
                    nova["QT"] = int(qtd)
                    linhas.append(nova)

            return pd.DataFrame(linhas) if linhas else pd.DataFrame(columns=id_vars + ["CategoriaIndigena", "Grupo", "Etapa", "QT"])

        # sem total e sem colunas por etapa → nada a fazer
        return pd.DataFrame(columns=id_vars + ["CategoriaIndigena", "Grupo", "Etapa", "QT"])

    # --- Docentes
    doc_tot_escola = expandir_grupo(df_final, docentes_geral, "Docentes", "QT", mask_cat_escola, "Escola Indígena")
    doc_tot_terra  = expandir_grupo(df_final, docentes_geral, "Docentes", "QT", mask_cat_terra,  "Em Terra Indígena")
    doc_tot_lingua = expandir_grupo(df_final, docentes_geral, "Docentes", "QT", mask_cat_lingua, "Com Língua Indígena")

    cols_doc_reais = [c.upper() for c in etapas_docentes_reais.values()]
    existem_doc_reais = any(c in df_final.columns for c in cols_doc_reais)
    doc_reais_escola = doc_reais_terra = doc_reais_lingua = pd.DataFrame()

    if USAR_DOCENTES_POR_ETAPA_SE_EXISTIR and existem_doc_reais:
        doc_reais_escola = expandir_grupo(df_final, etapas_docentes_reais, "Docentes", "QT", mask_cat_escola, "Escola Indígena")
        doc_reais_terra  = expandir_grupo(df_final, etapas_docentes_reais, "Docentes", "QT", mask_cat_terra,  "Em Terra Indígena")
        doc_reais_lingua = expandir_grupo(df_final, etapas_docentes_reais, "Docentes", "QT", mask_cat_lingua, "Com Língua Indígena")
    else:
        print("ℹ Não encontrei colunas QT_DOC_* (docentes por etapa). Vou estimar se habilitado.")

    doc_est_escola = doc_est_terra = doc_est_lingua = pd.DataFrame()
    if ESTIMAR_DOCENTES_POR_ETAPA and not existem_doc_reais:
        for col in etapas_matriculas_gerais.values():
            if col in df_final.columns:
                df_final[col] = to_int_series(df_final[col])
            else:
                df_final[col] = 0

        mat_cols = list(etapas_matriculas_gerais.values())
        df_final["_MAT_TOTAL_ESCOLA"] = df_final[mat_cols].sum(axis=1)

        if "QT_DOC_BAS" in df_final.columns:
            df_final["QT_DOC_BAS"] = to_int_series(df_final["QT_DOC_BAS"])
        else:
            df_final["QT_DOC_BAS"] = 0

        def estimar_docentes(mask_cat, categoria_nome: str) -> pd.DataFrame:
            base2 = df_final.loc[mask_cat].copy()
            linhas2 = []
            for _, row in base2.iterrows():
                total_doc = int(row["QT_DOC_BAS"])
                total_mat = int(row["_MAT_TOTAL_ESCOLA"])
                if total_doc <= 0 or total_mat <= 0:
                    continue

                etapas_presentes, pesos = [], []
                for etapa, col in etapas_matriculas_gerais.items():
                    m = int(row[col])
                    if m > 0:
                        etapas_presentes.append(etapa)
                        pesos.append(m)
                if not pesos:
                    continue

                pesos = np.array(pesos, dtype=float)
                frac = pesos / pesos.sum()
                estimados = np.floor(frac * total_doc).astype(int)
                restante = total_doc - estimados.sum()
                ordem = np.argsort(-(frac * total_doc - estimados))
                for k in ordem[:restante]:
                    estimados[k] += 1

                for etapa, qtd in zip(etapas_presentes, estimados):
                    if qtd <= 0:
                        continue
                    nova = {k: row.get(k) for k in id_vars}
                    nova["CategoriaIndigena"] = categoria_nome
                    nova["Grupo"] = "Docentes (Estimado)"
                    nova["Etapa"] = etapa
                    nova["QT"] = int(qtd)
                    linhas2.append(nova)
            return pd.DataFrame(linhas2) if linhas2 else pd.DataFrame()

        doc_est_escola = estimar_docentes(mask_cat_escola, "Escola Indígena")
        doc_est_terra  = estimar_docentes(mask_cat_terra,  "Em Terra Indígena")
        doc_est_lingua = estimar_docentes(mask_cat_lingua, "Com Língua Indígena")

    # --- Monta blocos
    dfs_indig = [
        selecionar_cols(esc_escola), selecionar_cols(esc_terra), selecionar_cols(esc_lingua),
        selecionar_cols(mat_indigena_total(mask_cat_escola, "Escola Indígena")),
        selecionar_cols(mat_indigena_total(mask_cat_terra,  "Em Terra Indígena")),
        selecionar_cols(mat_indigena_total(mask_cat_lingua, "Com Língua Indígena")),
        selecionar_cols(mat_indigena_etapas(mask_cat_escola, "Escola Indígena")),
        selecionar_cols(mat_indigena_etapas(mask_cat_terra,  "Em Terra Indígena")),
        selecionar_cols(mat_indigena_etapas(mask_cat_lingua, "Com Língua Indígena")),
    ]

    # Docentes: OU o total geral, OU o detalhamento por etapa, nunca os dois
    # (o detalhamento soma exatamente ao total => evitaria duplicação).
    doc_por_etapa_indig = [
        doc_reais_escola, doc_reais_terra, doc_reais_lingua,
        doc_est_escola,   doc_est_terra,   doc_est_lingua,
    ]
    tem_doc_por_etapa_indig = any(
        d is not None and not d.empty for d in doc_por_etapa_indig
    )

    if tem_doc_por_etapa_indig:
        for df_x in doc_por_etapa_indig:
            if df_x is not None and not df_x.empty:
                dfs_indig.append(selecionar_cols(df_x))
    else:
        dfs_indig += [
            selecionar_cols(doc_tot_escola), selecionar_cols(doc_tot_terra), selecionar_cols(doc_tot_lingua),
        ]

    # (opcional) incluir matrículas gerais? (default False para evitar confusão)
    if INCLUIR_MATRICULAS_GERAIS_NO_INDIGENA:
        mat_escola = expandir_grupo(df_final, etapas_matriculas_gerais, "Matrículas (GERAL)", "QT", mask_cat_escola, "Escola Indígena")
        mat_terra  = expandir_grupo(df_final, etapas_matriculas_gerais, "Matrículas (GERAL)", "QT", mask_cat_terra,  "Em Terra Indígena")
        mat_lingua = expandir_grupo(df_final, etapas_matriculas_gerais, "Matrículas (GERAL)", "QT", mask_cat_lingua, "Com Língua Indígena")
        dfs_indig += [selecionar_cols(mat_escola), selecionar_cols(mat_terra), selecionar_cols(mat_lingua)]

    # garantir unicidade e descartar vazios
    dfs_indig = [ensure_unique_columns(d) for d in dfs_indig if d is not None and not d.empty]

    if not dfs_indig:
        df_indig = pd.DataFrame(columns=[*(c for c in ID_VARS_CANDIDATAS if c in df_final.columns),
                                         "CategoriaIndigena", "Grupo", "Etapa", "QT"])
    else:
        df_indig = pd.concat(dfs_indig, ignore_index=True, sort=False)

    # ordenação padrão
    ordem = [c for c in [
        "NU_ANO_CENSO", "SG_UF", "CO_MUNICIPIO", "NO_MUNICIPIO",
        "TP_DEPENDENCIA", "TP_LOCALIZACAO", "CO_ENTIDADE", "NO_ENTIDADE",
        "CategoriaIndigena", "Grupo", "Etapa", "QT"
    ] if c in df_indig.columns]

    if ordem:
        df_indig = df_indig[ordem].sort_values(ordem).reset_index(drop=True)

    df_indig.to_csv(ARQUIVO_INDIGENA, index=False, encoding="utf-8")
    print(f"✅ Indígena normalizado salvo: {ARQUIVO_INDIGENA} | Linhas: {len(df_indig):,}")

    # (opcional) checagem de consistência: soma etapas = total indígena
    try:
        if col_total_indig and not df_indig.empty and {"CO_ENTIDADE", "NU_ANO_CENSO"} <= set(df_final.columns):
            chave = [c for c in ["NU_ANO_CENSO", "CO_ENTIDADE"] if c in df_final.columns]

            total_indig = df_final[chave + [col_total_indig]].copy()
            total_indig[col_total_indig] = to_int_series(total_indig[col_total_indig])
            total_indig = total_indig.groupby(chave, as_index=False)[col_total_indig].sum()

            etapas_long = df_indig[df_indig["Grupo"].eq("Matrículas Indígenas (Etapas)")]
            if not etapas_long.empty and set(chave) <= set(etapas_long.columns):
                soma_por_escola = etapas_long.groupby(chave, as_index=False)["QT"].sum().rename(columns={"QT": "SOMA_ETAPAS"})
                chk = pd.merge(total_indig, soma_por_escola, on=chave, how="left").fillna(0)
                diff = (chk[col_total_indig] - chk["SOMA_ETAPAS"]).abs().sum()
                print(f"🔎 Checagem: |Total indígena - soma etapas| acumulado = {int(diff):,}")
    except Exception:
        print("ℹ Checagem de consistência ignorada (opcional).")


if __name__ == "__main__":
    normalizar_indigena()
