#!/usr/bin/env python3
# main.py (enxuto – só coleta/processamento)
# -*- coding: utf-8 -*-
import sys
import argparse
from config import (
    DATA_DIR, RAW_DIR, EXTRACT_DIR, MICRODADOS_DIR, OUT_DIR, UF_TARGET,
    ARQUIVO_SAIDA_BRUTO, ARQUIVO_NORMALIZADO, ARQUIVO_INDIGENA,
    ARQUIVO_SIOPE, ARQUIVO_INFRA, ARQUIVO_TX_REND_LONG
)

import coleta_censo
import normaliza_censo
import normaliza_indigena
import coleta_siope
import normaliza_infra
import normaliza_tx_rendimento
import load_db_from_csv as loader
import db

def step_coleta_censo():
    print("\n=== [1] COLETA CENSO ===")
    arquivos = coleta_censo.coletar_censo()
    print(f"✔ CSVs em: {MICRODADOS_DIR} | {len(arquivos)} arquivo(s).")

def step_normaliza_censo():
    print("\n=== [2] NORMALIZAÇÃO GERAL (Censo) ===")
    normaliza_censo.normalizar_censo()
    print(f"✔ OUT: {ARQUIVO_SAIDA_BRUTO} | {ARQUIVO_NORMALIZADO}")

def step_normaliza_indigena():
    print("\n=== [3] NORMALIZAÇÃO INDÍGENA (Censo) ===")
    normaliza_indigena.normalizar_indigena()
    print(f"✔ OUT: {ARQUIVO_INDIGENA}")

def step_normaliza_infra():
    print("\n=== [4] INFRAESTRUTURA (Censo) ===")
    normaliza_infra.normalizar_infra()
    print(f"✔ OUT: {ARQUIVO_INFRA}")

def step_coleta_siope():
    print("\n=== [5] COLETA SIOPE ===")
    df = coleta_siope.coletar_siope()
    linhas = len(df) if df is not None and not df.empty else 0
    print(f"✔ OUT: {ARQUIVO_SIOPE} | Linhas: {linhas:,}")

def step_tx_rendimento():
    print("\n=== [6] TAXA DE RENDIMENTO (Municípios) ===")
    normaliza_tx_rendimento.normalizar_tx_rendimento()
    print(f"✔ OUT: {ARQUIVO_TX_REND_LONG}")


def run_all():
    step_coleta_censo()
    step_normaliza_censo()
    step_normaliza_indigena()
    step_normaliza_infra()
    step_coleta_siope()
    step_tx_rendimento()
    print("\n✅ Pipeline completo finalizado (somente local).")

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Pipeline de automação (local: coleta + processamento)")
    parser.add_argument(
        "--step",
        choices=["coleta_censo","normaliza_censo","normaliza_indigena",
                 "normaliza_infra","coleta_siope","tx_rendimento","all"],
        required=True
    )
    return parser.parse_args(argv)

def main(argv=None):
    args = parse_args(argv)
    for p in [DATA_DIR, RAW_DIR, EXTRACT_DIR, MICRODADOS_DIR, OUT_DIR]:
        p.mkdir(parents=True, exist_ok=True)

    print(f"UF alvo: {UF_TARGET}")

    if args.step == "coleta_censo":
        step_coleta_censo()
    elif args.step == "normaliza_censo":
        step_normaliza_censo()
    elif args.step == "normaliza_indigena":
        step_normaliza_indigena()
    elif args.step == "normaliza_infra":
        step_normaliza_infra()
    elif args.step == "coleta_siope":
        step_coleta_siope()
    elif args.step == "tx_rendimento":
        step_tx_rendimento()
    elif args.step == "all":
        run_all()

if __name__ == "__main__":
    main(sys.argv[1:])
