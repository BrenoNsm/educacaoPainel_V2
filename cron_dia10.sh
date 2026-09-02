#!/usr/bin/env bash
# cron_dia10.sh
# Script para ser executado via crontab no dia 10 de cada mês.
# Faz o download e processamento completo do pipeline educacaoPainel.
#
# Instalação no crontab (executar como usuário dono do projeto):
#   crontab -e
#   Adicione a linha:
#     0 6 10 * * /caminho/para/educacaoPainel/cron_dia10.sh
#   (executa todo dia 10 às 06:00)
#
# Para persistir no PostgreSQL, passe a flag --db:
#     0 6 10 * * /caminho/para/educacaoPainel/cron_dia10.sh --db

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Carrega profile para ter PATH completo (necessário em cron)
if [ -f "$HOME/.profile" ]; then
    # shellcheck disable=SC1090,SC1091
    source "$HOME/.profile"
fi
if [ -f "$HOME/.bashrc" ]; then
    # shellcheck disable=SC1090,SC1091
    source "$HOME/.bashrc"
fi

export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"

# Verifica se python3 está disponível
if ! command -v python3 &>/dev/null; then
    echo "[cron_dia10] ERRO: python3 não encontrado no PATH"
    exit 1
fi

echo "[cron_dia10] Iniciando pipeline em $PROJECT_DIR"
echo "[cron_dia10] $(date '+%Y-%m-%d %H:%M:%S')"

# Por padrão persiste no banco (--db). Use --local para apenas CSVs.
"$PROJECT_DIR/run.sh" "${1:---db}"

echo "[cron_dia10] Pipeline concluído em $(date '+%Y-%m-%d %H:%M:%S')"
