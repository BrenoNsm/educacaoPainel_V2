# coleta_censo.py
# -*- coding: utf-8 -*-
"""
MÃ³dulo de coleta do Censo Escolar (INEP).
- Faz download automÃ¡tico dos arquivos ZIP por ano.
- Extrai o conteÃºdo.
- Localiza e copia o CSV de microdados para a pasta microDados/.
"""

import requests
import zipfile
import shutil
import glob
import os
import re
from pathlib import Path
import pandas as pd
import truststore
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
truststore.inject_into_ssl()

from config import (
    RAW_DIR, EXTRACT_DIR, MICRODADOS_DIR,
    CENSO_YEARS, CENSO_URL_TEMPLATE,
    CENSO_CSV_GLOB_CANDIDATES,
    CENSO_TABELA_GLOB, CENSO_TABELAS_MERGE, CENSO_TABELA_CHAVE,
)


def _session() -> requests.Session:
    """Sessão HTTP com tentativas automáticas.
    O servidor do INEP costuma derrubar conexões (ConnectionResetError 10054)
    de forma transitória; sem retry o HEAD falha e o pipeline "trava".
    """
    retries = Retry(
        total=4,
        connect=4,
        read=4,
        status=4,
        redirect=4,
        backoff_factor=1.0,          # 1s, 2s, 4s... entre tentativas
        status_forcelist=[408, 429, 500, 502, 503, 504],
        raise_on_status=False,       # 404/4xx não vira exceção
    )
    sess = requests.Session()
    adapter = HTTPAdapter(max_retries=retries)
    sess.mount("https://", adapter)
    sess.mount("http://", adapter)
    return sess

def baixar_zip(ano: int) -> Path:
    """
    Baixa o ZIP do Censo Escolar para a pasta RAW_DIR.
    Tenta mÃºltiplos padrÃµes de URL atÃ© encontrar um vÃ¡lido (HTTP 200).
    """
    destino = RAW_DIR / f"censo_escolar_{ano}.zip"

    if destino.exists():
        print(f" Já existe: {destino}")
        return destino

# Tenta cada padrão de URL até achar um que funcione
    sess = _session()
    url_encontrada = None
    for pattern in CENSO_URL_TEMPLATE:
        url = pattern.format(year=ano)
        try:
            # HEAD é mais leve: só verifica se o arquivo existe
            response = sess.head(url, timeout=30, allow_redirects=True, verify=True)
            if response.status_code == 200:
                url_encontrada = url
                print(f"🔍 URL válida encontrada: {url}")
                break
            elif response.status_code == 404:
                print(f"ℹ️ {url} -> 404 (arquivo ainda não publicado).")
            else:
                print(f"ℹ️ {url} -> HTTP {response.status_code}.")
        except requests.RequestException as e:
            print(f"⚠️ Falha ao testar {url}: {e}")
            continue  # Tenta o próximo padrão

    if not url_encontrada:
        raise ConnectionError(f"❌ Nenhuma URL válida encontrada para o ano {ano}")

    # Agora faz o download real com GET (mesma sessão com retry)
    print(f"⬇️ Baixando {url_encontrada} ...")
    r = sess.get(url_encontrada, stream=True, timeout=300, verify=True)
    r.raise_for_status()
    
    with open(destino, "wb") as f:
        shutil.copyfileobj(r.raw, f)

    print(f" Baixado: {destino}")
    return destino

def extrair_zip(zip_path: Path, ano: int) -> Path:
    """Extrai o ZIP baixado para a pasta EXTRACT_DIR/ano."""
    destino = EXTRACT_DIR / str(ano)
    if destino.exists():
        print(f"Já extrai­do: {destino}")
        return destino

    print(f"Extraindo {zip_path} ...")
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(destino)

    print(f"Extrai­do em {destino}")
    return destino

def localizar_csv(diretorio: Path, ano: int) -> Path:
    """
    Procura o CSV principal de microdados dentro do diretÃ³rio extraÃ­do.
    Retorna o caminho do arquivo encontrado.
    """
    for pattern in CENSO_CSV_GLOB_CANDIDATES:
        matches = list(diretorio.glob(pattern))
        if matches:
            # pega o primeiro encontrado
            csv_path = matches[0]
            destino = MICRODADOS_DIR / f"microdados_{ano}.csv"
            shutil.copy(csv_path, destino)
            print(f"CSV localizado/copied: {destino}")
            return destino

    # Formato 2025+: INEP dividiu o microdados único em Tabela_*.csv por tema.
    # Recombinamos as tabelas núcleo por escola em um único microdados_{ano}.csv.
    tabelas = list(diretorio.glob(CENSO_TABELA_GLOB))
    if tabelas:
        destino = MICRODADOS_DIR / f"microdados_{ano}.csv"
        return combinar_tabelas_split(tabelas, ano, destino)

    raise FileNotFoundError(f"Nenhum CSV de microdados encontrado em {diretorio}")


def combinar_tabelas_split(tabelas: list[Path], ano: int, destino: Path) -> Path:
    """
    Formato 2025+ do INEP: os microdados foram divididos em arquivos
    'Tabela_*.csv' (Escola, Matricula, Turma, Docente, ...), todos com a
    chave (NU_ANO_CENSO, CO_ENTIDADE). Junta as tabelas núcleo em um único
    CSV por escola (outer join), restaurando o formato dos anos anteriores.
    """
    chave = [c.upper() for c in CENSO_TABELA_CHAVE]
    alvos = {t.upper().replace("_", "") for t in CENSO_TABELAS_MERGE}

    def _tabela_alvo(path: Path) -> bool:
        m = re.match(r"Tabela_(.+?)_\d{4}", path.stem)
        if not m:
            return False
        return m.group(1).upper().replace("_", "") in alvos

    tabelas_nucleo = sorted(t for t in tabelas if _tabela_alvo(t))
    if not tabelas_nucleo:
        raise FileNotFoundError(
            f"Nenhuma tabela núcleo ({CENSO_TABELAS_MERGE}) encontrada no formato 2025+."
        )

    print(f"Formato 2025+ detectado. Recombinando {len(tabelas_nucleo)} tabelas por escola...")
    base = None
    for t in tabelas_nucleo:
        print(f"  Lendo {t.name} ...")
        df = pd.read_csv(
            t, sep=";", dtype=str, encoding="ISO-8859-1", low_memory=False
        )
        df.columns = [str(c).upper().strip() for c in df.columns]
        df = df.set_index([c for c in chave if c in df.columns])
        df = df.loc[:, ~df.columns.duplicated()]
        base = df if base is None else pd.concat([base, df], axis=1)

    base = base.reset_index()
    destino.parent.mkdir(parents=True, exist_ok=True)
    base.to_csv(destino, sep=";", index=False, encoding="ISO-8859-1")
    print(f"CSV recombinado (formato 2025+) salvo: {destino} | Linhas: {len(base):,}")
    return destino

def processar_ano(ano: int) -> Path:
    """Executa o pipeline completo para um ano do Censo."""
    zip_path = baixar_zip(ano)
    pasta_extraida = extrair_zip(zip_path, ano)
    csv_final = localizar_csv(pasta_extraida, ano)
    return csv_final

def coletar_censo():
    """Executa coleta para todos os anos configurados."""
    todos_csvs = []
    for ano in CENSO_YEARS:
        try:
            csv_path = processar_ano(ano)
            todos_csvs.append(csv_path)
        except Exception as e:
            print(f"Erro no ano {ano}: {e}")
    return todos_csvs

if __name__ == "__main__":
    arquivos = coletar_censo()
    print(f"\n Coleta concluÃ­da. {len(arquivos)} arquivos CSV disponÃ­veis em {MICRODADOS_DIR}")
