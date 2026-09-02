#!/usr/bin/env python3
"""
ingest_all_to_db.py
Orquestrador alternativo que executa as etapas e persiste no PostgreSQL,
mantendo os CSVs opcionais (config.SAVE_CSV).

Uso:
  python ingest_all_to_db.py --step all
  python ingest_all_to_db.py --step normaliza_censo
"""

from __future__ import annotations

import sys
import argparse

import config
import coleta_censo
import normaliza_censo
import normaliza_indigena
import normaliza_infra
import normaliza_tx_rendimento
import coleta_siope
import load_db_from_csv as loader
import db


def step_coleta_censo():
    print("\n=== [1] COLETA CENSO ===")
    arquivos = coleta_censo.coletar_censo()
    print(f"OK CSVs em: {config.MICRODADOS_DIR} | {len(arquivos)} arquivo(s).")


def step_normaliza_censo():
    print("\n=== [2] NORMALIZAÇÃO GERAL (Censo) ===")
    normaliza_censo.normalizar_censo()
    n = loader.carregar_censo_normalizado()
    print(f"OK Censo no DB: {n:,} linhas (vw_dados_normalizados_por_etapa)")


def step_normaliza_indigena():
    print("\n=== [3] NORMALIZAÇÃO INDÍGENA (Censo) ===")
    normaliza_indigena.normalizar_indigena()
    n = loader.carregar_indigena_normalizado()
    print(f"OK Indígena no DB: {n:,} linhas (vw_dados_indigena_normalizado)")


def step_normaliza_infra():
    print("\n=== [4] INFRAESTRUTURA (Censo) ===")
    normaliza_infra.normalizar_infra()
    n = loader.carregar_infra_long()
    print(f"OK Infra no DB: {n:,} linhas (vw_infra_escola_long)")


def step_coleta_siope():
    print("\n=== [5] COLETA SIOPE ===")
    df = coleta_siope.coletar_siope()
    linhas = len(df) if df is not None and not df.empty else 0
    if linhas:
        db.init_db()
        db.insert_siope_raw(df)
    print(f"OK SIOPE: {linhas:,} registros inseridos (siope_registro_raw)")


def step_tx_rendimento():
    print("\n=== [6] TAXA DE RENDIMENTO (Municípios) ===")
    normaliza_tx_rendimento.normalizar_tx_rendimento()
    n = loader.carregar_tx_rendimento_long()
    print(f"OK Tx Rendimento no DB: {n:,} linhas (vw_tx_rendimento_long)")


def run_all():
    step_coleta_censo()
    step_normaliza_censo()
    step_normaliza_indigena()
    step_normaliza_infra()
    step_coleta_siope()
    step_tx_rendimento()
    print("\nOK. Pipeline completo finalizado com persistência em PostgreSQL.")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Orquestrador com persistência em PostgreSQL")
    parser.add_argument(
        "--step",
        choices=[
            "coleta_censo","normaliza_censo","normaliza_indigena",
            "normaliza_infra","coleta_siope","tx_rendimento","all"
        ],
        required=True
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
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

