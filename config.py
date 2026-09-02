# -*- coding: utf-8 -*-
# config.py
"""
Configurações globais do Pipeline.
Ajuste aqui UF, anos do Censo, caminhos e parâmetros de coleta/normalização.
"""

from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import os
load_dotenv()
# ====== DIRETÓRIOS ======
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
EXTRACT_DIR = DATA_DIR / "extract"
MICRODADOS_DIR = DATA_DIR / "microDados"
OUT_DIR = DATA_DIR / "out"
INDICADORES_DIR = DATA_DIR / "indicadores"

# cria pastas se não existirem
for p in [DATA_DIR, RAW_DIR, EXTRACT_DIR, MICRODADOS_DIR, OUT_DIR, INDICADORES_DIR]:
    p.mkdir(parents=True, exist_ok=True)

# ====== PARÂMETROS GERAIS ======
UF_TARGET = "RR"                  # UF alvo (pode alterar)
LIMITE_COLS = 475                 # limite do dicionário (nº de colunas)
DICIONARIO_PATH = BASE_DIR / "Complementares" / "dicionário_dados_educação_básica.xlsx"

# ====== CENSO ESCOLAR (INEP) ======
# O Censo de um dado ano só é publicado no ano seguinte, por isso usamos
# `current_year` como limite EXCLUSIVO (2010..ano_atual-1). Incluir o ano
# atual sempre resultaria em 404 (arquivo ainda não publicado).
CENSO_YEARS = list(range(2010, datetime.now().year))  # 2010..ano_atual-1
CENSO_URL_TEMPLATE = [
    "https://download.inep.gov.br/dados_abertos/microdados_censo_escolar_{year}.zip",
    "https://download.inep.gov.br/dados_abertos/microdados_censo_escolar_{year}_.zip",
]
"""
NOME ESPERADO DO CSV DE INTERESSE DENTRO DO ZIP
Obs.: a estrutura interna varia por ano. Usamos padrões amplos (glob)
para localizar o arquivo de microdados.
"""
CENSO_CSV_GLOB_CANDIDATES = [
    "**/dados/microdados.csv",
    "**/DADOS/microdados.csv",
    "**/dados/*microdados*.csv",
    "**/DADOS/*microdados*.csv",
    "**/*microdados*.csv",
]
"""
FORMATO 2025+ (INEP dividiu o microdados único em arquivos por tema:
Tabela_Escola / Tabela_Matricula / Tabela_Turma / Tabela_Docente ...).
Nesses anos não existe um CSV 'microdados' único; recombinamos as
tabelas núcleo por escola em um único microdados_{ano}.csv.
"""
CENSO_TABELA_GLOB = "**/Tabela_*.csv"
CENSO_TABELAS_MERGE = ["Escola", "Matricula", "Turma", "Docente"]
CENSO_TABELA_CHAVE = ["NU_ANO_CENSO", "CO_ENTIDADE"]

# ====== SIOPE (FNDE) ======
SIOPE_BASE = "https://www.fnde.gov.br/olinda-ide/servico/DADOS_ABERTOS_SIOPE/versao/v1/odata"
SIOPE_RESOURCE = "Dados_Gerais_Siope"      # <- case correto do endpoint
SIOPE_START_YEAR = 2010                    # pode ajustar
SIOPE_TIMEOUT = 60                         # <- corrigido (antes estava TIMMEOUT)
SIOPE_SLEEP_BETWEEN = 10                   # segundos entre requisições (antes: SIOPE_SLEEP_BETWEEN_REQUESTS)
SIOPE_PERIOD_LABEL = {1: "Jan-Fev", 2: "Mar-Abr", 3: "Mai-Jun", 4: "Jul-Ago", 5: "Set-Out", 6: "Nov-Dez"}
ARQUIVO_SIOPE = OUT_DIR / "SIOPE_UF.csv"

# ====== ARQUIVOS DE SAÍDA (Censo) ======
ARQUIVO_SAIDA_BRUTO = OUT_DIR / "censo_escolar_UF.csv"
ARQUIVO_NORMALIZADO = OUT_DIR / "dados_normalizados_por_etapa.csv"
ARQUIVO_INDIGENA = OUT_DIR / "dados_indigena_normalizado.csv"  # <- singular p/ casar com módulos
ARQUIVO_INFRA = OUT_DIR / "infra_escola_long.csv"

# ====== CSV / ENCODINGS ======
CSV_SEP = ";"
ENCODING_INPUTS = ["ISO-8859-1", "utf-8"]  # <- corrigido (antes ENCONDING_INPUTS)
ENCODING_OUT_DEFAULT = "utf-8"             # <- corrigido (antes ENCONDING_OUT_DEFAULT)
ENCODING_OUT_LATIN = "ISO-8859-1"          # <- corrigido (antes ENCONDING_OUT_LATIN)

# ====== PERSISTÊNCIA / BANCO DE DADOS ======
# Definições de conexão PostgreSQL (ambiente local)
# Ajuste a senha abaixo conforme seu ambiente local.
PG_HOST = os.getenv("DB_Host")
PG_PORT = os.getenv("DB_Port")
PG_DATABASE = os.getenv("DB_Database")
PG_USER = os.getenv("DB_user")
PG_PASSWORD = os.getenv("DB_Password")

# Desabilita escrita de CSVs finais (manter apenas no banco)
SAVE_CSV = False

# ============================================================
# CONTROLES DE PROCESSAMENTO (Docentes por etapa)
# (comentário explicativo já fornecido anteriormente)
# ============================================================

# nomes exatamente como usados nos módulos
USAR_DOCENTES_POR_ETAPA_SE_EXISTIR = True   # <- corrigido (antes USAR_DOCENTE_POR_ETAPA_SE_EXISTIR)
ESTIMAR_DOCENTES_POR_ETAPA = True

# ====== COLUNAS / IDS PADRÃO ======
ID_VARS_CANDIDATAS = [
    "NU_ANO_CENSO", "SG_UF", "CO_MUNICIPIO", "NO_MUNICIPIO",
    "TP_DEPENDENCIA", "TP_LOCALIZACAO", "CO_ENTIDADE", "NO_ENTIDADE",
]

# ====== TAXA DE RENDIMENTO (ESCOLAS) ======
# Anos a processar (ajuste como quiser: ex. range(2019, 2025))
TX_REND_YEARS = list(range(2020, datetime.now().year + 1))

# Fonte (ZIP por ano) — MUNICÍPIOS
# Variações históricas de URL por ano (ordem importa; tentamos de cima para baixo)
# >>> AQUI PRECISA SER UMA LISTA *FLAT* DE STRINGS, SEM LISTAS ANINHADAS <<<
TX_REND_URL_PATTERNS_MUN = [
    # 2012
    "https://download.inep.gov.br/informacoes_estatisticas/indicadores_educacionais/{year}/taxas_rendimento/tx_rendimento_municipios_{year}.zip",
    # 2013..2015
    "https://download.inep.gov.br/informacoes_estatisticas/indicadores_educacionais/{year}/taxa_rendimento/tx_rendimento_municipios_{year}.zip",
    # 2016
    "https://download.inep.gov.br/informacoes_estatisticas/indicadores_educacionais/{year}/TAXA_REND_{year}_MUNICIPIOS.zip",
    # 2017
    "https://download.inep.gov.br/informacoes_estatisticas/indicadores_educacionais/{year}/TAXA_REND_{year}_MUNICIPIOS.zip",
    # 2018
    "https://download.inep.gov.br/informacoes_estatisticas/indicadores_educacionais/{year}/TX_REND_MUNICIPIOS_{year}.zip",
    # 2019..2024
    "https://download.inep.gov.br/informacoes_estatisticas/indicadores_educacionais/{year}/tx_rend_municipios_{year}.zip",
]

# Procura do XLS/XLSX dentro do ZIP (há anos com pastas repetidas e nomes diferentes)
TX_REND_GLOB_MUNICIPIOS = [
    "**/tx_rendimento_municipios_{year}.xlsx",
    "**/tx_rendimento_municipios_{year}.xls",
    "**/tx_rend_municipios_{year}.xlsx",
    "**/tx_rend_municipios_{year}.xls",
    "**/TX_REND_MUNICIPIOS_{year}.xlsx",
    "**/TX_REND_MUNICIPIOS_{year}.xls",
    "**/TAXA_REND_{year}_MUNICIPIOS.xlsx",
    "**/TAXA_REND_{year}_MUNICIPIOS.xls",
    "**/tx_rendimento_municipios_{year}/tx_rendimento_municipios_{year}.xlsx",
    "**/tx_rendimento_municipios_{year}/tx_rendimento_municipios_{year}.xls",
    "**/tx_rend_municipios_{year}/tx_rend_municipios_{year}.xlsx",
    "**/tx_rend_municipios_{year}/tx_rend_municipios_{year}.xls",
    "**/*.xlsx",
    "**/*.xls",
]

# Abas possíveis do Excel para MUNICÍPIOS
TX_REND_SHEET_CANDIDATES = ["MUNICÍPIOS", "MUNICIPIOS"]
# ÚNICA saída desejada
ARQUIVO_TX_REND_LONG = OUT_DIR / "dados_RR_por_serie_long.csv"

# ======================
# GOOGLE SHEETS / LOOKER (Service Account)
# ======================
GOOGLE_SERVICE_ACCOUNT_FILE = BASE_DIR / "secrets" / "sa_credentials.json"  # coloque seu JSON aqui
GOOGLE_OAUTH_CLIENT_SECRET_FILE = BASE_DIR / "secrets" / "client_secret.json"
GOOGLE_OAUTH_TOKEN_FILE = BASE_DIR / "secrets" / "token.json"
GOOGLE_DRIVE_FOLDER_ID = ""  # ID da pasta alvo no Drive
SHEET_ID_PAINEL_RR = ""


# Quais CSVs subir como Planilha Google (um CSV = uma planilha)
# Itens a importar (um CSV -> uma aba dentro da planilha acima)
# Quais CSVs subir como **Planilha Google nativa** (um CSV = um arquivo no Drive)
UPLOAD_CSV_AS_SHEET = [
    {
        "csv_path": OUT_DIR / "censo_escolar_UF.csv",
        "sheet_name": "censo_escolar_UF",
        "replace": True,
    },
    {
        "csv_path": OUT_DIR / "dados_indigena_normalizado.csv",
        "sheet_name": "dados_indigena_normalizado",
        "replace": True,
    },
    {
        "csv_path": OUT_DIR / "dados_normalizados_por_etapa.csv",
        "sheet_name": "dados_normalizados_por_etapa",
        "replace": True,
    },
    {
        "csv_path": OUT_DIR / "dados_RR_por_serie_long.csv",
        "sheet_name": "dados_RR_por_serie_long",
        "replace": True,
    },
    {
        "csv_path": OUT_DIR / "infra_escola_long.csv",
        "sheet_name": "infra_escola_long",
        "replace": True,
    },
    {
        "csv_path": OUT_DIR / "SIOPE_UF.csv",
        "sheet_name": "SIOPE_UF",
        "replace": True,
    },
]

INCLUIR_MATRICULAS_GERAIS_NO_INDIGENA = True
