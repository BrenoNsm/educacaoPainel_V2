# Documentação: Como Rodar o Projeto

## 1. Pré-requisitos

- **Python 3.9+**
- **PostgreSQL** (apenas se for usar `ingest_all_to_db.py`)

### Instalação das Dependências

```bash
pip install -r requirements.txt
```

---

## 2. Configuração (.env)

Crie um arquivo `.env` na raiz com as credenciais do PostgreSQL:

```ini
DB_Host = 10.10.x.x
DB_Port = 5432
DB_Database = painel_educacao
DB_user = postgres
DB_Password = sua_senha
```

---

## 3. Modos de Execução

### A. Pipeline Local (apenas CSVs)

```bash
python3 main.py --step all
```

### B. Pipeline com Banco de Dados

```bash
python3 ingest_all_to_db.py --step all
```

### C. Usando run.sh (automático)

```bash
# Com persistência PostgreSQL (padrão)
./run.sh

# Apenas CSVs
./run.sh --local
```

O script cria virtual environment, instala dependências e executa o pipeline com logging.

---

## 4. Execução Automática (cron) — Dia 10 de Cada Mês

Para rodar o pipeline automaticamente todo dia 10:

### Usando cron_dia10.sh

```bash
# Torne o script executável
chmod +x cron_dia10.sh run.sh

# Edite o crontab
crontab -e

# Adicione uma das linhas abaixo:
# (executa dia 10 às 06:00 da manhã — com persistência no banco por padrão)
0 6 10 * * /caminho/completo/para/educacaoPainel/cron_dia10.sh

# Para apenas CSVs locais:
0 6 10 * * /caminho/completo/para/educacaoPainel/cron_dia10.sh --local
```

### Verificar se o cron está ativo:

```bash
crontab -l
# Deve mostrar a linha agendada
```

### Logs

Os logs são salvos em `logs/pipeline_YYYY-MM-DD_HH-MM-SS.log`.

---

## 5. Estrutura de Pastas

```
data/
├── raw/           # Zips baixados
├── extract/       # Conteúdo extraído
├── microDados/    # CSVs brutos do Censo
└── out/           # CSVs processados
logs/              # Logs do pipeline
```

## 6. Resolução de Problemas

- **python3 não encontrado**: `sudo apt install python3 python3-venv`
- **Erro de conexão DB**: Verifique `.env` e firewall
- **Database não existe**: Crie manualmente via `CREATE DATABASE painel_educacao;`
