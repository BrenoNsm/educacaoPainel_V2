# normaliza_tx_rendimento.py
# -*- coding: utf-8 -*-
"""
Taxa de Rendimento (MUNICÍPIOS/ESCOLAS) — Baixa, extrai, processa e gera APENAS o CSV longo:
    config.ARQUIVO_TX_REND_LONG  (ex.: data/out/dados_RR_por_serie_long.csv)

Robustez:
- Tenta múltiplos templates de URL (config.TX_REND_URL_PATTERNS_MUN)
- Acha .xls/.xlsx com vários globs (config.TX_REND_GLOB_MUNICIPIOS)
- Se os globs falharem: varre toda a pasta extraída e escolhe o melhor arquivo
- Detecta automaticamente a aba (prioriza nomes com 'MUNIC', aceita 'ESCOLAS' como fallback)
- Testa vários skiprows (5,6,4,7,8,9) até achar cabeçalho em 2 níveis com 'UF' e métricas
- Lê .xlsx com openpyxl e .xls com xlrd==1.2.0
"""

from __future__ import annotations

import re
import time
import shutil
import zipfile
from pathlib import Path

import pandas as pd
import requests

import truststore
truststore.inject_into_ssl()

import config  # usar prefixo config.X


# =============================
# Utils / Helpers
# =============================
def _flatten_str_list(maybe_list) -> list[str]:
    """Achata listas/tuplas aninhadas e retorna apenas strings."""
    out: list[str] = []
    if isinstance(maybe_list, (list, tuple)):
        for it in maybe_list:
            if isinstance(it, (list, tuple)):
                out.extend([s for s in it if isinstance(s, str)])
            elif isinstance(it, str):
                out.append(it)
    elif isinstance(maybe_list, str):
        out.append(maybe_list)
    return out


def _engine_for_suffix(path: Path) -> str | None:
    suf = path.suffix.lower()
    if suf == ".xls":
        return "xlrd"   # requer xlrd==1.2.0
    return None         # openpyxl (padrão do pandas) para .xlsx


# =============================
# Download / Extração
# =============================
def _download_zip_municipios(year: int) -> Path:
    """
    Tenta múltiplos templates de URL definidos em config.TX_REND_URL_PATTERNS_MUN.
    Evita re-download se o arquivo já existir.
    """
    destino = config.RAW_DIR / "rendimento" / f"tx_rendimento_municipios_{year}.zip"
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists():
        print(f"✔️ ZIP já existe: {destino}")
        return destino

    url_templates = _flatten_str_list(getattr(config, "TX_REND_URL_PATTERNS_MUN", []))
    if not url_templates:
        raise RuntimeError("TX_REND_URL_PATTERNS_MUN vazio/indefinido no config.")

    last_err: Exception | str | None = None
    for tpl in url_templates:
        url = tpl.format(year=year)
        print(f"⬇️ Tentando {url} ...")
        for tent in range(2):  # retry simples por template
            try:
                r = requests.get(url, stream=True, timeout=90)
                if r.status_code == 404:
                    last_err = f"404 em {url}"
                    break
                r.raise_for_status()
                with open(destino, "wb") as f:
                    shutil.copyfileobj(r.raw, f)
                print(f"✅ Baixado: {destino}")
                return destino
            except Exception as e:
                last_err = e
                print(f"⚠️ Falha (tentativa {tent+1}): {e}")
                time.sleep(2 + tent)
    raise RuntimeError(f"Falha ao baixar {year}. Último erro: {last_err}")


def _extract_zip(zip_path: Path, year: int) -> Path:
    """Extrai uma única vez para data/extract/rendimento/<ano>_municipios/."""
    outdir = config.EXTRACT_DIR / "rendimento" / f"{year}_municipios"
    if outdir.exists():
        print(f"✔️ Já extraído: {outdir}")
        return outdir
    print(f"📦 Extraindo {zip_path} ...")
    outdir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(outdir)
    print(f"✅ Extraído em: {outdir}")
    return outdir


def _find_xls_or_xlsx(extract_dir: Path, year: int) -> Path:
    """
    1) Tenta padrões do config (globs).
    2) Se não achar, varre recursivamente por *.xlsx / *.xls.
       - Se só houver 1 arquivo, retorna.
       - Se houver vários, ranqueia por nome (~municip|rend) e tamanho, e retorna o melhor.
    """
    patterns = _flatten_str_list(getattr(config, "TX_REND_GLOB_MUNICIPIOS", []))

    # 1) tenta padrões do config
    candidatos: list[Path] = []
    for patt in patterns or []:
        try:
            patt_res = patt.format(year=year)
        except Exception:
            continue
        candidatos.extend(sorted(extract_dir.glob(patt_res)))

    # 2) fallback: varredura recursiva
    if not candidatos:
        encontrados = list(extract_dir.rglob("*.xlsx")) + list(extract_dir.rglob("*.xls"))
        if not encontrados:
            raise FileNotFoundError(f"Não encontrei XLS/XLSX para {year} em {extract_dir}.")
        if len(encontrados) == 1:
            return encontrados[0]

        def score(p: Path) -> tuple[int, int]:
            name = p.name.lower()
            bonus = 0
            if re.search(r"munic|municíp", name):
                bonus += 2
            if re.search(r"rend|rendimento", name):
                bonus += 1
            try:
                size = p.stat().st_size
            except Exception:
                size = 0
            return (bonus, size)

        candidatos = sorted(encontrados, key=score, reverse=True)

    return candidatos[0]


# =============================
# Leitura / Parsing
# =============================
METRICAS = {"Taxa de Aprovação", "Taxa de Reprovação", "Taxa de Abandono"}

ID_COLS_PRIORIDADE = [
    "Ano", "Região", "UF", "Código do Município", "Nome do Município",
    "Código da Escola", "Nome da Escola", "Localização", "Dependência Administrativa",
]


def _pick_sheet_name(xls: pd.ExcelFile) -> str:
    """
    Escolhe a aba de forma robusta:
    - prioriza nomes contendo 'MUNIC' (municípios),
    - senão nomes contendo 'ESCOL',
    - senão a primeira aba.
    """
    names = [str(s) for s in xls.sheet_names]
    cand_mun = [s for s in names if "munic" in s.lower()]
    if cand_mun:
        return cand_mun[0]
    cand_esc = [s for s in names if "escol" in s.lower()]
    if cand_esc:
        return cand_esc[0]
    return names[0]


def _read_any(xlsx_path: Path) -> pd.DataFrame:
    """
    Tenta múltiplos skiprows (5,6,4,7,8,9) e cabeçalho de 2 níveis.
    Retorna o primeiro DataFrame que contenha coluna 'UF' e colunas de métricas.
    """
    engine = _engine_for_suffix(xlsx_path)
    xls = pd.ExcelFile(xlsx_path, engine=engine)
    sheet = _pick_sheet_name(xls)

    last_err: Exception | None = None
    for skip in (5, 6, 4, 7, 8, 9):
        try:
            df = pd.read_excel(xlsx_path, sheet_name=sheet, skiprows=skip, header=[0, 1], engine=engine)

            # achata header: para métricas concatena nível 0 e 1
            def _flat(col):
                if isinstance(col, tuple):
                    a, b = col
                    if a in METRICAS:
                        return f"{a}__{'' if b is None else str(b).strip()}"
                    return str(a).strip()
                return str(col).strip()

            df.columns = [_flat(c) for c in df.columns]
            df.columns = [c.strip() for c in df.columns]

            if "UF" not in df.columns:
                continue
            metric_cols = [c for c in df.columns if c.startswith("Taxa de ")]
            if not metric_cols:
                continue

            return df
        except Exception as e:
            last_err = e
            continue

    raise RuntimeError(f"Falha ao ler a planilha em {xlsx_path}. Último erro: {last_err}")


def _limpar_valor_para_numero(x: object):
    """Converte '87,3%', '--', '', '93,1' → float 0-100; vazio/ruído → pd.NA."""
    if pd.isna(x):
        return pd.NA
    s = str(x).strip()
    if s in ("", "--"):
        return pd.NA
    s = s.replace("%", "").replace(",", ".")
    m = re.search(r"[-+]?\d*\.?\d+", s)
    if not m:
        return pd.NA
    try:
        return float(m.group(0))
    except Exception:
        return pd.NA


def _parse_etapa_serie(sub: str):
    """
    Recebe sufixo após '__' (ex.: 'Ensino Fundamental.Ano.0').
    Retorna ("EF"/"EM"/"Outro", serie_int|None), onde série = idx+1 quando houver.
    """
    s = str(sub or "")
    s_norm = s.lower()
    m = re.search(r"\.(\d+)$", s)
    idx = int(m.group(1)) if m else None
    if "ensino fundamental" in s_norm:
        return "EF", (idx + 1 if idx is not None else None)
    if "ensino médio" in s_norm or "ensino medio" in s_norm:
        return "EM", (idx + 1 if idx is not None else None)
    return "Outro", None


def _processar_arquivo(xlsx_path: Path) -> pd.DataFrame:
    """Lê, filtra UF, derrete métricas e padroniza formato longo para um arquivo."""
    print(f"📖 Lendo: {xlsx_path.name}")
    df = _read_any(xlsx_path)

    id_cols = [c for c in ID_COLS_PRIORIDADE if c in df.columns]
    if not id_cols:
        raise RuntimeError("Nenhuma coluna de identificação padrão foi encontrada.")

    # filtra UF alvo
    df = df[df["UF"] == config.UF_TARGET].copy()

    # métricas (tudo que começa com 'Taxa de ')
    metric_cols = [c for c in df.columns if c.startswith("Taxa de ")]
    if not metric_cols:
        raise RuntimeError("Não encontrei colunas de métricas (Aprovação/Reprovação/Abandono).")

    # formato longo
    df_long = df.melt(
        id_vars=id_cols,
        value_vars=metric_cols,
        var_name="MetricaSub",
        value_name="Valor",
    )

    # separar "Métrica" e sufixo "Sub"
    split = df_long["MetricaSub"].str.split("__", n=1, expand=True)
    df_long["Métrica"] = split[0]
    df_long["Sub"] = split[1].fillna("")

    # Etapa/Série
    etapa_serie = df_long["Sub"].apply(_parse_etapa_serie)
    df_long["Etapa"] = etapa_serie.apply(lambda x: x[0])
    df_long["Serie"] = etapa_serie.apply(lambda x: x[1])

    # mantém só EF/EM
    df_long = df_long[df_long["Etapa"].isin(["EF", "EM"])].copy()

    # numéricos (0-100 e 0-1)
    df_long["Valor_num"] = df_long["Valor"].apply(_limpar_valor_para_numero)   # 0-100
    df_long["Valor_prop"] = (df_long["Valor_num"] / 100).astype("Float64")     # 0-1

    # ordenação/colunas finais
    cols_out = id_cols + ["Etapa", "Serie", "Métrica", "Valor", "Valor_num", "Valor_prop"]
    df_long = (
        df_long[cols_out]
        .sort_values(id_cols + ["Etapa", "Serie", "Métrica"])
        .reset_index(drop=True)
    )
    return df_long


# =============================
# Orquestração do step
# =============================
def normalizar_tx_rendimento():
    """Baixa, extrai, processa e escreve APENAS o CSV longo (UF == config.UF_TARGET)."""
    frames: list[pd.DataFrame] = []
    anos = list(getattr(config, "TX_REND_YEARS", []))
    if not anos:
        raise RuntimeError("TX_REND_YEARS vazio/indefinido no config.")
    for year in anos:
        try:
            zip_path   = _download_zip_municipios(year)
            extract_dir= _extract_zip(zip_path, year)
            xlsx_path  = _find_xls_or_xlsx(extract_dir, year)
            frames.append(_processar_arquivo(xlsx_path))
        except Exception as e:
            print(f"❌ Falha no ano {year}: {e}")

    if not frames:
        raise RuntimeError("Nenhum dado processado para Taxa de Rendimento.")

    final_long = pd.concat(frames, ignore_index=True)
    config.ARQUIVO_TX_REND_LONG.parent.mkdir(parents=True, exist_ok=True)
    final_long.to_csv(config.ARQUIVO_TX_REND_LONG, index=False, encoding="utf-8")
    print(f"\n✅ Salvo apenas o CSV longo: {config.ARQUIVO_TX_REND_LONG} | Linhas: {len(final_long):,}")


if __name__ == "__main__":
    normalizar_tx_rendimento()