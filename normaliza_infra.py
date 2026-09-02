# normaliza_infra.py
# -*- coding: utf-8 -*-
"""
Normalização de infraestrutura escolar (formato longo por escola).

• Lê todos os CSVs do Censo em data/microDados/ (gerados pelo coleta_censo.py)
• Filtra por UF (config.UF_TARGET)
• Detecta variáveis de infraestrutura via dicionário (aba microdados_unidade_coleta)
• Converte itens (0/1) e gera dataset longo: GrupoInfra, Item, POSSUI
• Salva em data/out/infra_escola_long.csv
"""

import os, glob, re
from pathlib import Path
import pandas as pd
import numpy as np
import chardet

import config  # use sempre com prefixo: config.X

# ======= AJUSTES DO MÓDULO =======
ARQ_SAIDA_ESCOLA = config.OUT_DIR / "infra_escola_long.csv"

# Palavras-chave para achar colunas de infraestrutura no dicionário
INFRA_PATTERNS = {
    "Água":            r"^IN_AGUA_|^IN_AGUA$|POTAVEL|FILTRADA",
    "Energia":         r"^IN_ENERGIA_|^IN_ENERGIA$|RENOVAVEL|GERADOR",
    "Esgoto":          r"^IN_ESGOTO_",
    "Lixo":            r"^IN_LIXO_|^IN_TRATAMENTO_LIXO_",
    "Internet/TIC":    r"^IN_INTERNET|^IN_ACESSO_INTERNET|COMPUT|^IN_EQUIP_|^IN_REDE_",
    "Dependências":    r"^IN_BANHEI|^IN_BANHEIRO|^IN_BIBLI|^IN_SALA_|^IN_LABORATORIO|^IN_AUDITORIO|^IN_COZINHA|^IN_DORMITORIO|^IN_QUADRA|^IN_REFEITORIO|^IN_ALMOXARIFADO|^IN_PATIO|^IN_PARQUE_INFANTIL",
    "Acessibilidade":  r"ACESSIB|RAMP|ELEVADOR|SINAL|CORRIMAO|PICTO|BRAILLE|PNE|DEFIC|^IN_ACESSIBILIDADE",
}

ID_COLS = [
    "NU_ANO_CENSO","SG_UF","CO_MUNICIPIO","NO_MUNICIPIO",
    "TP_DEPENDENCIA","TP_LOCALIZACAO","CO_ENTIDADE","NO_ENTIDADE"
]

# ======= FUNÇÕES AUXILIARES =======
def detectar_encoding(caminho: Path, nbytes: int = 200_000) -> str:
    with open(caminho, "rb") as f:
        raw = f.read(nbytes)
    return chardet.detect(raw).get("encoding") or "utf-8"

def ler_csv_flex(caminho: Path) -> pd.DataFrame:
    """Lê CSV detectando encoding e separador (vírgula/; ou \\t), padroniza colunas em maiúsculas."""
    enc = detectar_encoding(caminho)
    try:
        df = pd.read_csv(caminho, engine="python", sep=None, dtype=str, encoding=enc, low_memory=False)
    except Exception:
        df = pd.read_csv(caminho, sep=";", dtype=str, encoding=enc, low_memory=False)
    df.columns = [str(c).upper().strip() for c in df.columns]
    return df

def listar_arquivos(pasta_microdados: Path) -> list[Path]:
    return sorted(Path(pasta_microdados).glob("*.csv"))

def carregar_variaveis_do_dicionario(path_excel: Path) -> pd.DataFrame:
    xls = pd.ExcelFile(path_excel)
    dic = xls.parse("microdados_unidade_coleta", header=None)
    dic = dic.iloc[9:, [1,2,3]]
    dic.columns = ["variavel","descricao","tipo"]
    dic["variavel"]  = dic["variavel"].astype(str).str.upper().str.strip()
    dic["descricao"] = dic["descricao"].astype(str).str.strip()
    dic["tipo"]      = dic["tipo"].astype(str).str.strip()
    return dic

def detectar_vars_infra(dic_df: pd.DataFrame) -> dict[str, list[str]]:
    encontrados: dict[str, list[str]] = {}
    for grupo, patt in INFRA_PATTERNS.items():
        regex = re.compile(patt, flags=re.IGNORECASE)
        mask = dic_df["variavel"].str.contains(regex)
        cols = sorted(dic_df.loc[mask, "variavel"].unique().tolist())
        if cols:
            encontrados[grupo] = cols
    # remove duplicatas entre grupos (prioriza a 1ª ocorrência)
    seen = set()
    for g in list(encontrados.keys()):
        exclusivos = [c for c in encontrados[g] if c not in seen]
        seen.update(exclusivos)
        encontrados[g] = exclusivos
    return encontrados

def to_int01(series_like) -> pd.Series:
    s = pd.Series(series_like, dtype="string").str.strip().str.upper()
    s = s.replace({
        "S":"1","SIM":"1","TRUE":"1","T":"1","X":"1",
        "N":"0","NAO":"0","NÃO":"0","FALSE":"0","F":"0"
    })
    out = pd.to_numeric(s, errors="coerce")
    return out.clip(lower=0, upper=1).astype("Int64")

def der_ano_if_needed(df: pd.DataFrame, caminho: Path) -> pd.DataFrame:
    if "NU_ANO_CENSO" not in df.columns:
        ano = "".join(ch for ch in caminho.stem if ch.isdigit())
        df["NU_ANO_CENSO"] = int(ano[:4]) if ano else pd.NA
    return df

def ensure_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df

def map_localizacao(tp_localizacao_series) -> pd.Series:
    s = pd.Series(tp_localizacao_series, dtype="string").str.strip().str.upper()
    cond_urb = s.isin(["1","URBANA","URBANO"])
    cond_rur = s.isin(["2","RURAL"])
    return pd.Series(np.where(cond_urb, "Urbana", np.where(cond_rur, "Rural", "Não informado")), index=s.index)

def map_rede(tp_dependencia_series) -> pd.Series:
    s = pd.Series(tp_dependencia_series, dtype="string").str.strip().str.upper()
    return pd.Series(
        np.where(s.isin(["1","FEDERAL"]), "Federal",
        np.where(s.isin(["2","ESTADUAL","ESTADO"]), "Estadual",
        np.where(s.isin(["3","MUNICIPAL","MUNICÍPAL"]), "Municipal",
        np.where(s.isin(["4","PRIVADA","PARTICULAR"]), "Privada", "Outros/Não informado")))),
        index=s.index
    )

# ======= PIPELINE =======
def normalizar_infra():
    print("🔍 Lendo dicionário e detectando variáveis de infraestrutura...")
    dic = carregar_variaveis_do_dicionario(config.DICIONARIO_PATH)
    vars_infra_por_grupo = detectar_vars_infra(dic)
    if not vars_infra_por_grupo:
        raise RuntimeError("Nenhuma variável de infraestrutura encontrada no dicionário com os padrões definidos.")

    print("Variáveis de Infraestrutura detectadas por grupo:")
    for g, cols in vars_infra_por_grupo.items():
        print(f" - {g}: {len(cols)} variáveis")

    arquivos = listar_arquivos(config.MICRODADOS_DIR)
    if not arquivos:
        raise FileNotFoundError(f"Nenhum CSV encontrado em '{config.MICRODADOS_DIR}'.")

    dfs = []
    for arq in arquivos:
        try:
            df = ler_csv_flex(arq)
            df = der_ano_if_needed(df, arq)
            df = ensure_cols(df, ID_COLS + ["SG_UF"])
            if config.UF_TARGET and "SG_UF" in df.columns:
                df = df[df["SG_UF"] == config.UF_TARGET]
            if not df.empty:
                dfs.append(df)
                print(f"✅ {arq.name} | linhas: {len(df):,} | colunas: {len(df.columns)}")
        except Exception as e:
            print(f"❌ Falha em {arq.name}: {e}")

    if not dfs:
        raise RuntimeError("Nenhum DataFrame foi carregado após o filtro de UF.")

    base = pd.concat(dfs, ignore_index=True)

    # 1) Deriva Localização e Rede
    if "TP_LOCALIZACAO" not in base.columns:
        base["TP_LOCALIZACAO"] = pd.NA
    if "TP_DEPENDENCIA" not in base.columns:
        base["TP_DEPENDENCIA"] = pd.NA

    base["LOCALIZACAO_TIPO"] = map_localizacao(base["TP_LOCALIZACAO"])
    base["REDE_TIPO"]        = map_rede(base["TP_DEPENDENCIA"])

    # 2) Seleciona variáveis de infraestrutura presentes
    todas_vars_infra = sorted({c for cols in vars_infra_por_grupo.values() for c in cols})
    presentes = [c for c in todas_vars_infra if c in base.columns]
    if not presentes:
        raise RuntimeError("Nenhuma variável de infraestrutura encontrada nos CSVs (após detecção pelo dicionário).")

    sub = base[ID_COLS + ["LOCALIZACAO_TIPO","REDE_TIPO"] + presentes].copy()

    # 3) Converte todas as variáveis de infra para 0/1
    for c in presentes:
        sub[c] = to_int01(sub[c])

    # 4) Mapeia Item -> GrupoInfra
    col2grupo: dict[str, str] = {}
    for g, cols in vars_infra_por_grupo.items():
        for c in cols:
            if c in presentes:
                col2grupo[c] = g

    # 5) Wide -> Long
    long = sub.melt(
        id_vars=ID_COLS + ["LOCALIZACAO_TIPO","REDE_TIPO"],
        value_vars=presentes,
        var_name="Item",
        value_name="POSSUI"
    )

    # 6) Limpa e tipa
    long = long.dropna(subset=["POSSUI"]).copy()
    long["POSSUI"] = long["POSSUI"].astype("Int64")
    long["GrupoInfra"] = long["Item"].map(col2grupo).fillna("Outros")

    # 7) Ordena e salva
    cols_final = [
        "NU_ANO_CENSO","SG_UF","CO_MUNICIPIO","NO_MUNICIPIO",
        "TP_DEPENDENCIA","REDE_TIPO","TP_LOCALIZACAO","LOCALIZACAO_TIPO",
        "CO_ENTIDADE","NO_ENTIDADE",
        "GrupoInfra","Item","POSSUI"
    ]
    long = long[cols_final].sort_values(
        ["NU_ANO_CENSO","SG_UF","NO_MUNICIPIO","CO_ENTIDADE","GrupoInfra","Item"]
    ).reset_index(drop=True)

    ARQ_SAIDA_ESCOLA.parent.mkdir(parents=True, exist_ok=True)
    long.to_csv(ARQ_SAIDA_ESCOLA, index=False, encoding="utf-8")
    print(f"\n✅ Salvo: {ARQ_SAIDA_ESCOLA} | Linhas: {len(long):,}")
    print("\nDica BI:")
    print("- KPI (% de escolas com o item) = SUM(POSSUI) / COUNT_DISTINCT(CO_ENTIDADE).")
    print("- Filtrar por LOCALIZACAO_TIPO (Urbana/Rural) e REDE_TIPO (Municipal/Estadual/Federal/Privada).")

if __name__ == "__main__":
    normalizar_infra()
