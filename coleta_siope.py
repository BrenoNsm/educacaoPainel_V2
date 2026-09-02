# coleta_siope.py
# -*- coding: utf-8 -*-
"""
Coleta de dados do SIOPE (FNDE) via OData:
- Consulta o recurso 'Dados_Gerais_Siope' por ano e período (1..6).
- Faz paginação usando @odata.nextLink.
- Consolida todas as colunas retornadas (schema pode variar por ano).
- Salva CSV final em config.ARQUIVO_SIOPE.
"""

import time
from datetime import datetime
from typing import List, Dict, Any, Optional

import requests
import pandas as pd

import truststore
truststore.inject_into_ssl()

from config import (
    UF_TARGET,
    ARQUIVO_SIOPE,
    SIOPE_BASE,
    SIOPE_RESOURCE,
    SIOPE_START_YEAR,
    SIOPE_TIMEOUT,
    SIOPE_SLEEP_BETWEEN,
    SIOPE_PERIOD_LABEL,
)

def _odata_url(ano: int, num_peri: int, sig_uf: str) -> str:
    """
    Monta a URL do endpoint OData conforme padrão do FNDE.
    Ex.: .../Dados_Gerais_Siope(Ano_Consulta=@Ano_Consulta,Num_Peri=@Num_Peri,Sig_UF=@Sig_UF)?@Ano_Consulta=2023&@Num_Peri=1&@Sig_UF='RR'&format=json
    """
    base_fn = f"{SIOPE_BASE}/{SIOPE_RESOURCE}(Ano_Consulta=@Ano_Consulta,Num_Peri=@Num_Peri,Sig_UF=@Sig_UF)"
    return (
        f"{base_fn}?@Ano_Consulta={ano}"
        f"&@Num_Peri={num_peri}"
        f"&@Sig_UF='{sig_uf}'"
        f"&format=json"
    )

def _fetch_paged(url: str, timeout: int = SIOPE_TIMEOUT, sleep_between: float = SIOPE_SLEEP_BETWEEN) -> List[Dict[str, Any]]:
    """
    Faz GET paginado no endpoint OData, seguindo @odata.nextLink.
    Retorna a lista completa de registros (dicts).
    """
    results: List[Dict[str, Any]] = []
    guard = 0
    while url and guard < 200:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        data = r.json()

        page = data.get("value", [])
        if not isinstance(page, list):
            raise RuntimeError("Resposta inesperada do SIOPE: campo 'value' não é lista")

        results.extend(page)

        # múltiplas variantes possíveis para nextLink
        url = data.get("@odata.nextLink") or data.get("odata.nextLink") or data.get("nextLink")
        guard += 1
        if url:
            time.sleep(sleep_between)
    return results

def fetch_one_period(ano: int, num_peri: int, sig_uf: str) -> pd.DataFrame:
    """
    Coleta um período específico (1..6) de um ano do SIOPE.
    Adiciona coluna 'PERIODO_LABEL' usando SIOPE_PERIOD_LABEL.
    """
    url = _odata_url(ano, num_peri, sig_uf)
    rows = _fetch_paged(url)
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame.from_records(rows)  # union de chaves → colunas
    df["NUM_ANO"] = ano
    df["NUM_PERI"] = num_peri
    df["PERIODO_LABEL"] = SIOPE_PERIOD_LABEL.get(num_peri, "")
    return df

def fetch_range(sig_uf: Optional[str] = None, start_year: Optional[int] = None, end_year: Optional[int] = None) -> pd.DataFrame:
    """
    Coleta uma faixa de anos e períodos para uma UF (default: config.UF_TARGET).
    - start_year padrão: SIOPE_START_YEAR
    - end_year padrão: ano corrente
    """
    uf = (sig_uf or UF_TARGET).upper()
    sy = start_year or SIOPE_START_YEAR
    ey = end_year or datetime.now().year

    dfs: List[pd.DataFrame] = []
    for year in range(sy, ey + 1):
        for per in range(1, 7):
            try:
                print(f"🔎 SIOPE {uf} | {year} P{per} ...")
                dfp = fetch_one_period(year, per, uf)
                if not dfp.empty:
                    dfs.append(dfp)
            except Exception as e:
                print(f"❌ Falha em {year} P{per}: {e}")
            time.sleep(SIOPE_SLEEP_BETWEEN)

    if not dfs:
        return pd.DataFrame()

    all_df = pd.concat(dfs, ignore_index=True, sort=False)

    # Ordena se existirem as colunas usuais
    for col in ("NUM_ANO", "NUM_PERI"):
        if col in all_df.columns:
            all_df[col] = pd.to_numeric(all_df[col], errors="coerce")

    sort_cols = [c for c in ["NUM_ANO", "NUM_PERI", "SIG_UF", "COD_MUNI"] if c in all_df.columns]
    if sort_cols:
        all_df = all_df.sort_values(sort_cols, kind="stable").reset_index(drop=True)

    return all_df

def coletar_siope(sig_uf: Optional[str] = None, start_year: Optional[int] = None, end_year: Optional[int] = None) -> pd.DataFrame:
    """
    Função de alto nível para coletar e salvar o CSV final do SIOPE.
    Retorna o DataFrame consolidado.
    """
    df = fetch_range(sig_uf=sig_uf, start_year=start_year, end_year=end_year)
    if df.empty:
        print("⚠ Nenhum dado retornado pelo SIOPE.")
        return df

    df.to_csv(ARQUIVO_SIOPE, index=False, encoding="utf-8-sig")
    print(f"✅ SIOPE salvo em {ARQUIVO_SIOPE} | Linhas: {len(df):,} | Colunas: {len(df.columns)}")
    return df

if __name__ == "__main__":
    coletar_siope()
