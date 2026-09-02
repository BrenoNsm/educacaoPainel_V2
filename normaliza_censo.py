# normaliza_censo.py
# -*- coding: utf-8 -*-
"""
Normalização do Censo Escolar:
- Lê todos os CSVs em data/ (gerados pelo coleta_censo.py).
- Aplica dicionário de tipos (planilha microdados_unidade_coleta).
- Padroniza nomes e converte tipos.
- Filtra pela UF alvo (config.UF_TARGET).
- Normaliza em formato longo (Matrículas, Turmas, Docentes).
- Estima docentes por etapa quando não existirem colunas QT_DOC_*.
- Salva:
   - censo_escolar_UF.csv (dump filtrado por UF)
   - dados_normalizados_por_etapa.csv (dataset longo consolidado)
"""

import os, glob
import numpy as np
import pandas as pd
from pathlib import Path

from config import (
    MICRODADOS_DIR, DICIONARIO_PATH,
    ARQUIVO_SAIDA_BRUTO, ARQUIVO_NORMALIZADO,
    UF_TARGET, LIMITE_COLS,
    USAR_DOCENTES_POR_ETAPA_SE_EXISTIR, ESTIMAR_DOCENTES_POR_ETAPA,
    ID_VARS_CANDIDATAS,
)

# ==========================
# FUNÇÕES AUXILIARES
# ==========================

def carregar_dicionario_tipos(path_excel: Path, limite: int = LIMITE_COLS):
    """
    Lê nomes e tipos da aba 'microdados_unidade_coleta' do dicionário.
    Retorna:
      - nomes: lista de nomes de colunas referenciais (até 'limite')
      - dict_tipos: mapeamento {coluna: tipo pandas desejado}
    """
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
    """
    Lê CSV sep=';' tentando encodings comuns.
    - Mantém header do arquivo quando existir.
    - Se vier sem header (colunas '0','1',...), aplica nomes do dicionário quando possível.
    - Converte tipos apenas nas colunas existentes.
    """
    # 1) tenta ISO-8859-1
    try:
        df = pd.read_csv(
            caminho,
            encoding='ISO-8859-1',
            sep=';',
            header=0,
            na_values=[".", "", "NA", "NaN"],
            dtype=str,
            low_memory=False
        )
    except UnicodeDecodeError:
        # 2) fallback UTF-8
        df = pd.read_csv(
            caminho,
            encoding='utf-8',
            sep=';',
            header=0,
            na_values=[".", "", "NA", "NaN"],
            dtype=str,
            low_memory=False
        )

    # padroniza nomes
    df.columns = [str(c).upper().strip() for c in df.columns]

    # caso raro: veio sem header (0,1,2,...)
    if all(col.isdigit() for col in df.columns):
        if df.shape[1] >= len(nomes_ref):
            df = df.iloc[:, :len(nomes_ref)]
            df.columns = [c.upper().strip() for c in nomes_ref]

    # Converte tipos conforme dicionário SOMENTE para colunas presentes
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
            elif t == 'string':
                df[col_up] = pd.Series(df[col_up], dtype="string")

    return df


def to_int_series(serie) -> pd.Series:
    """Converte série para Int64 a partir de string/float, tratando milhar/decimal."""
    return (
        pd.to_numeric(
            pd.Series(serie, dtype="string")
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
            .str.strip(),
            errors="coerce"
        ).fillna(0).astype("Int64")
    )


def expandir_grupo(df: pd.DataFrame, mapeamento: dict, nome_grupo: str, nome_valor: str = "QT") -> pd.DataFrame:
    """
    Expande colunas largas (ex.: QT_MAT_*, QT_TUR_*, QT_DOC_*) para formato longo:
    retorna linhas com colunas originais + ['Grupo','Etapa',nome_valor]
    apenas para valores != 0.
    """
    linhas = []
    for etapa, coluna in mapeamento.items():
        col_up = coluna.upper().strip()
        if col_up in df.columns:
            serie = df[col_up]
            if not pd.api.types.is_integer_dtype(serie):
                serie = to_int_series(serie)
            mask = serie.fillna(0).ne(0)
            if mask.any():
                bloco = df.loc[mask].copy()
                bloco["Grupo"] = nome_grupo
                bloco["Etapa"] = etapa
                bloco[nome_valor] = serie[mask].astype("Int64")
                linhas.append(bloco)

    if not linhas:
        return pd.DataFrame(columns=list(df.columns) + ["Grupo", "Etapa", nome_valor])
    return pd.concat(linhas, ignore_index=True)


# ==========================
# PIPELINE PRINCIPAL
# ==========================

def normalizar_censo():
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

            # tenta inferir NU_ANO_CENSO a partir do nome do arquivo
            if 'NU_ANO_CENSO' in df.columns:
                ano = ''.join(filter(str.isdigit, p.stem))
                if ano.isdigit():
                    df['NU_ANO_CENSO'] = int(ano)

            # filtra UF se coluna existir
            if 'SG_UF' in df.columns:
                df = df[df['SG_UF'] == UF_TARGET]

            dfs.append(df)
        except Exception as e:
            print(f"❌ Erro em {p.name}: {e}")

    if not dfs:
        raise RuntimeError("Nenhum DataFrame foi carregado com sucesso.")

    df_final = pd.concat(dfs, ignore_index=True)
    # dump bruto filtrado
    df_final.to_csv(ARQUIVO_SAIDA_BRUTO, index=False, encoding='ISO-8859-1')
    print(f"✅ Arquivo bruto filtrado salvo: {ARQUIVO_SAIDA_BRUTO} | Linhas: {len(df_final):,}")

    print("🔁 Normalizando (formato longo)...")

    # --- MAPEAMENTOS ---
    etapas_matriculas = {
        "Educação Especial": "QT_MAT_ESP",
        "Ed. Infantil - Creche": "QT_MAT_INF_CRE",
        "Ed. Infantil - Creche - Tempo Integral": "QT_MAT_INF_CRE_INT",
        "Ed. Infantil - Pré-Escola": "QT_MAT_INF_PRE",
        "Ed. Infantil - Pré-Escola - Tempo Integral": "QT_MAT_INF_PRE_INT",
        "Ensino Fund. - Anos Iniciais": "QT_MAT_FUND_AI",
        "Ensino Fund. - Anos Iniciais - Tempo Integral": "QT_MAT_FUND_AI_INT",
        "Ensino Fund. - Anos Finais": "QT_MAT_FUND_AF",
        "Ensino Fund. - Anos Finais - Tempo Integral": "QT_MAT_FUND_AF_INT",
        "Ensino Médio": "QT_MAT_MED",
        "Ensino Médio - Tempo Integral": "QT_MAT_MED_INT",
        "EJA - Ensino Fundamental": "QT_MAT_EJA_FUND",
        "EJA - Ensino Médio": "QT_MAT_EJA_MED",
    }

    etapas_turmas = {
        "Educação Especial": "QT_TUR_ESP",
        "Ed. Infantil - Creche": "QT_TUR_INF_CRE",
        "Ed. Infantil - Pré-Escola": "QT_TUR_INF_PRE",
        "Ensino Fund. - Anos Iniciais": "QT_TUR_FUND_AI",
        "Ensino Fund. - Anos Finais": "QT_TUR_FUND_AF",
        "Ensino Médio": "QT_TUR_MED",
        "EJA - Ensino Fundamental": "QT_TUR_EJA_FUND",
        "EJA - Ensino Médio": "QT_TUR_EJA_MED",
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

    # IDs para o BI
    id_vars = [c for c in ID_VARS_CANDIDATAS if c in df_final.columns]

    def selecionar_cols(df_long: pd.DataFrame) -> pd.DataFrame:
        cols = id_vars + ["Grupo", "Etapa", "QT"]
        return df_long.loc[:, [c for c in cols if c in df_long.columns]]

    # --- Matrículas e Turmas ---
    mat_long = expandir_grupo(df_final, etapas_matriculas, "Matrículas", "QT")
    tur_long = expandir_grupo(df_final, etapas_turmas, "Turmas", "QT")

    # --- Docentes: total geral ---
    doc_total_long = expandir_grupo(df_final, docentes_geral, "Docentes", "QT")

    # --- Docentes: por etapa (reais) se existirem colunas QT_DOC_* ---
    doc_por_etapa_reais = pd.DataFrame()
    if USAR_DOCENTES_POR_ETAPA_SE_EXISTIR:
        cols_doc_reais = [c.upper() for c in etapas_docentes_reais.values()]
        existem = [c for c in cols_doc_reais if c in df_final.columns]
        if existem:
            doc_por_etapa_reais = expandir_grupo(df_final, etapas_docentes_reais, "Docentes", "QT")
            print(f"✅ Docentes por etapa (reais) encontrados: {len(doc_por_etapa_reais):,} linhas.")
        else:
            print("ℹ Não encontrei colunas QT_DOC_* na base. (Podemos estimar pelos pesos de matrículas).")

    # --- Docentes: por etapa (estimado) quando não existirem colunas reais ---
    doc_por_etapa_estimado = pd.DataFrame()
    if ESTIMAR_DOCENTES_POR_ETAPA and doc_por_etapa_reais.empty:
        # garante numérico nas matrículas e no total de docentes
        for col in etapas_matriculas.values():
            if col in df_final.columns:
                df_final[col] = to_int_series(df_final[col])
            else:
                df_final[col] = 0

        mat_cols = list(etapas_matriculas.values())
        df_final["_MAT_TOTAL_ESCOLA"] = df_final[mat_cols].sum(axis=1)

        if "QT_DOC_BAS" in df_final.columns:
            df_final["QT_DOC_BAS"] = to_int_series(df_final["QT_DOC_BAS"])
        else:
            df_final["QT_DOC_BAS"] = 0

        linhas = []
        for _, row in df_final.iterrows():
            total_doc = int(row["QT_DOC_BAS"])
            total_mat = int(row["_MAT_TOTAL_ESCOLA"])
            if total_doc <= 0 or total_mat <= 0:
                continue

            # calcula frações por etapa (apenas etapas com matrícula > 0)
            etapas_presentes, pesos = [], []
            for etapa, col in etapas_matriculas.items():
                m = int(row[col])
                if m > 0:
                    etapas_presentes.append(etapa)
                    pesos.append(m)

            if not pesos:
                continue

            pesos = np.array(pesos, dtype=float)
            frac = pesos / pesos.sum()

            # arredondamento por "maior resto" para manter o total
            estimados = np.floor(frac * total_doc).astype(int)
            restante = total_doc - estimados.sum()
            ordem = np.argsort(-frac)
            for k in ordem[:restante]:
                estimados[k] += 1

            base = row.to_dict()
            for etapa, qtd in zip(etapas_presentes, estimados):
                if qtd <= 0:
                    continue
                nova = {**base}
                nova["Grupo"] = "Docentes (Estimado)"
                nova["Etapa"] = etapa
                nova["QT"] = int(qtd)
                linhas.append(nova)

        doc_por_etapa_estimado = pd.DataFrame(linhas) if linhas else pd.DataFrame()
        if not doc_por_etapa_estimado.empty:
            print(f"✅ Docentes por etapa (estimado) gerados: {len(doc_por_etapa_estimado):,} linhas.")
        else:
            print("ℹ Não foi possível estimar docentes por etapa (faltam matrículas/total).")

    # ==========================
    # CONSOLIDAÇÃO E SAÍDA
    # ==========================
    dfs_long = [
        selecionar_cols(mat_long),
        selecionar_cols(tur_long),
        selecionar_cols(doc_total_long),
    ]

    # inclui docentes por etapa reais/estimados conforme disponível
    if not doc_por_etapa_reais.empty:
        dfs_long.append(selecionar_cols(doc_por_etapa_reais))
    elif not doc_por_etapa_estimado.empty:
        dfs_long.append(selecionar_cols(doc_por_etapa_estimado))

    df_norm = pd.concat([d for d in dfs_long if not d.empty], ignore_index=True)

    # ordena colunas e linhas
    ordem = [c for c in [
        "NU_ANO_CENSO", "SG_UF", "CO_MUNICIPIO", "NO_MUNICIPIO",
        "TP_DEPENDENCIA", "TP_LOCALIZACAO", "CO_ENTIDADE", "NO_ENTIDADE",
        "Grupo", "Etapa", "QT"
    ] if c in df_norm.columns]

    if ordem:
        df_norm = df_norm[ordem].sort_values(ordem).reset_index(drop=True)

    # salva normalizado
    df_norm.to_csv(ARQUIVO_NORMALIZADO, index=False, encoding="utf-8")
    print(f"✅ Normalizado salvo: {ARQUIVO_NORMALIZADO} | Linhas: {len(df_norm):,}")

    # Resumo rápido
    if "Grupo" in df_norm.columns:
        print("\nResumo (linhas por Grupo):")
        print(df_norm.groupby("Grupo").size().sort_values(ascending=False))


if __name__ == "__main__":
    normalizar_censo()
