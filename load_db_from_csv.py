"""
load_db_from_csv.py
Carrega arquivos CSV gerados pelo pipeline e insere no PostgreSQL via db.py.
Usado como integração sem alterar a lógica dos módulos de normalização.
"""

from __future__ import annotations

import pandas as pd
import config
import db


def carregar_censo_normalizado():
    try:
        df = pd.read_csv(config.ARQUIVO_NORMALIZADO, dtype=str)
    except FileNotFoundError:
        return 0
    # tipa QT
    if "QT" in df.columns:
        df["QT"] = pd.to_numeric(df["QT"], errors="coerce").astype("Int64")
    db.init_db()
    db.upsert_municipios_from_df(df)
    db.upsert_escolas_from_df(df)
    db.insert_censo_medidas(df)
    return len(df)


def carregar_infra_long():
    try:
        df = pd.read_csv(config.ARQUIVO_INFRA, dtype=str)
    except FileNotFoundError:
        return 0
    # tipa POSSUI
    if "POSSUI" in df.columns:
        df["POSSUI"] = pd.to_numeric(df["POSSUI"], errors="coerce").fillna(0).astype("Int64")
    db.init_db()
    db.upsert_municipios_from_df(df.rename(columns={"SG_UF":"SG_UF"}))
    db.upsert_escolas_from_df(df.rename(columns={"CO_MUNICIPIO":"CO_MUNICIPIO"}))
    db.insert_infra_escola(df)
    return len(df)


def carregar_indigena_normalizado():
    try:
        df = pd.read_csv(config.ARQUIVO_INDIGENA, dtype=str)
    except FileNotFoundError:
        return 0
    if "QT" in df.columns:
        df["QT"] = pd.to_numeric(df["QT"], errors="coerce").astype("Int64")
    db.init_db()
    db.upsert_municipios_from_df(df)
    db.upsert_escolas_from_df(df)
    db.insert_indigena(df)
    return len(df)


def carregar_tx_rendimento_long():
    try:
        df = pd.read_csv(config.ARQUIVO_TX_REND_LONG, dtype=str)
    except FileNotFoundError:
        return 0
    # tipa números
    if "Valor_num" in df.columns:
        df["Valor_num"] = pd.to_numeric(df["Valor_num"], errors="coerce")
    if "Valor_prop" in df.columns:
        df["Valor_prop"] = pd.to_numeric(df["Valor_prop"], errors="coerce")

    db.init_db()
    # upsert de municípios com UF/nome quando possível
    muni_cols = [c for c in ["Código do Município","Nome do Município","UF"] if c in df.columns]
    if len(muni_cols) == 3:
        muni = df[["Código do Município","Nome do Município","UF"]].drop_duplicates()
        muni.columns = ["CO_MUNICIPIO","NO_MUNICIPIO","SG_UF"]
        db.upsert_municipios_from_df(muni)

    db.insert_tx_rendimento(df)
    return len(df)

