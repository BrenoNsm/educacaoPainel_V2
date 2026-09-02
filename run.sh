#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
LOG_DIR="$PROJECT_DIR/logs"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
LOG_FILE="$LOG_DIR/pipeline_$TIMESTAMP.log"

# === Modo de execução ===
# --db  : executa ingest_all_to_db.py (com persistência PostgreSQL) [padrão]
# --local : executa main.py (apenas CSVs)
MODE="${1:---db}"
USE_DB=false
if [ "$MODE" = "--db" ]; then
    USE_DB=true
fi

mkdir -p "$LOG_DIR"

# Carrega variáveis do .env (se existir) para conectar ao banco em modo cron
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    . "$PROJECT_DIR/.env"
    set +a
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Criando virtual environment..." | tee -a "$LOG_FILE"
    python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Instalando dependências..." | tee -a "$LOG_FILE"
pip install -q -r "$PROJECT_DIR/requirements.txt"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Iniciando pipeline completo..." | tee -a "$LOG_FILE"
cd "$PROJECT_DIR"

if [ "$USE_DB" = true ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Modo: com persistência em PostgreSQL" | tee -a "$LOG_FILE"
    python3 ingest_all_to_db.py --step all 2>&1 | tee -a "$LOG_FILE"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Modo: apenas CSVs locais" | tee -a "$LOG_FILE"
    python3 main.py --step all 2>&1 | tee -a "$LOG_FILE"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Pipeline finalizado." | tee -a "$LOG_FILE"
