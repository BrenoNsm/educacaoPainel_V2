-- DDL do banco (PostgreSQL) para o projeto painelEduca
-- Tabelas
CREATE TABLE IF NOT EXISTS dim_municipio (
    cod_municipio TEXT PRIMARY KEY,
    nome          TEXT,
    uf            TEXT
);

CREATE TABLE IF NOT EXISTS dim_escola (
    cod_escola     TEXT PRIMARY KEY,
    nome           TEXT,
    cod_municipio  TEXT REFERENCES dim_municipio(cod_municipio)
);

CREATE TABLE IF NOT EXISTS fact_censo_medida (
    ano             INT,
    uf              TEXT,
    cod_municipio   TEXT,
    nome_municipio  TEXT,
    tp_dependencia  TEXT,
    tp_localizacao  TEXT,
    cod_escola      TEXT,
    nome_escola     TEXT,
    grupo           TEXT,
    etapa           TEXT,
    qt              INT,
    CONSTRAINT pk_fact_censo_medida UNIQUE (ano, cod_escola, grupo, etapa)
);

CREATE TABLE IF NOT EXISTS fact_infra_escola (
    ano               INT,
    uf                TEXT,
    cod_municipio     TEXT,
    nome_municipio    TEXT,
    tp_dependencia    TEXT,
    rede_tipo         TEXT,
    tp_localizacao    TEXT,
    localizacao_tipo  TEXT,
    cod_escola        TEXT,
    nome_escola       TEXT,
    grupo_infra       TEXT,
    item              TEXT,
    possui            INT,
    CONSTRAINT pk_fact_infra_escola UNIQUE (ano, cod_escola, item)
);

CREATE TABLE IF NOT EXISTS fact_indigena (
    ano             INT,
    uf              TEXT,
    cod_municipio   TEXT,
    nome_municipio  TEXT,
    tp_dependencia  TEXT,
    tp_localizacao  TEXT,
    cod_escola      TEXT,
    nome_escola     TEXT,
    categoria       TEXT,
    grupo           TEXT,
    etapa           TEXT,
    qt              INT,
    CONSTRAINT pk_fact_indigena UNIQUE (ano, cod_escola, categoria, grupo, etapa)
);

CREATE TABLE IF NOT EXISTS fact_tx_rendimento (
    ano                 INT,
    regiao              TEXT,
    uf                  TEXT,
    cod_municipio       TEXT,
    nome_municipio      TEXT,
    cod_escola          TEXT,
    nome_escola         TEXT,
    localizacao         TEXT,
    dependencia         TEXT,
    etapa               TEXT,
    serie               INT,
    metrica             TEXT,
    valor               TEXT,
    valor_num           DOUBLE PRECISION,
    valor_prop          DOUBLE PRECISION,
    CONSTRAINT pk_fact_tx_rendimento UNIQUE (ano, uf, cod_municipio, cod_escola, etapa, serie, metrica)
);

CREATE TABLE IF NOT EXISTS siope_registro_raw (
    id             BIGSERIAL PRIMARY KEY,
    num_ano        INT,
    num_peri       INT,
    sig_uf         TEXT,
    cod_muni       TEXT,
    periodo_label  TEXT,
    payload        JSONB
);

-- Views
CREATE OR REPLACE VIEW vw_dados_normalizados_por_etapa AS
SELECT
    ano            AS "NU_ANO_CENSO",
    uf             AS "SG_UF",
    cod_municipio  AS "CO_MUNICIPIO",
    nome_municipio AS "NO_MUNICIPIO",
    tp_dependencia AS "TP_DEPENDENCIA",
    tp_localizacao AS "TP_LOCALIZACAO",
    cod_escola     AS "CO_ENTIDADE",
    nome_escola    AS "NO_ENTIDADE",
    grupo          AS "Grupo",
    etapa          AS "Etapa",
    qt             AS "QT"
FROM fact_censo_medida;

CREATE OR REPLACE VIEW vw_infra_escola_long AS
SELECT
    ano              AS "NU_ANO_CENSO",
    uf               AS "SG_UF",
    cod_municipio    AS "CO_MUNICIPIO",
    nome_municipio   AS "NO_MUNICIPIO",
    tp_dependencia   AS "TP_DEPENDENCIA",
    rede_tipo        AS "REDE_TIPO",
    tp_localizacao   AS "TP_LOCALIZACAO",
    localizacao_tipo AS "LOCALIZACAO_TIPO",
    cod_escola       AS "CO_ENTIDADE",
    nome_escola      AS "NO_ENTIDADE",
    grupo_infra      AS "GrupoInfra",
    item             AS "Item",
    possui           AS "POSSUI"
FROM fact_infra_escola;

CREATE OR REPLACE VIEW vw_dados_indigena_normalizado AS
SELECT
    ano            AS "NU_ANO_CENSO",
    uf             AS "SG_UF",
    cod_municipio  AS "CO_MUNICIPIO",
    nome_municipio AS "NO_MUNICIPIO",
    tp_dependencia AS "TP_DEPENDENCIA",
    tp_localizacao AS "TP_LOCALIZACAO",
    cod_escola     AS "CO_ENTIDADE",
    nome_escola    AS "NO_ENTIDADE",
    categoria      AS "CategoriaIndigena",
    grupo          AS "Grupo",
    etapa          AS "Etapa",
    qt             AS "QT"
FROM fact_indigena;

CREATE OR REPLACE VIEW vw_tx_rendimento_long AS
SELECT
    ano                AS "Ano",
    regiao             AS "Região",
    uf                 AS "UF",
    cod_municipio      AS "Código do Município",
    nome_municipio     AS "Nome do Município",
    cod_escola         AS "Código da Escola",
    nome_escola        AS "Nome da Escola",
    localizacao        AS "Localização",
    dependencia        AS "Dependência Administrativa",
    etapa              AS "Etapa",
    serie              AS "Serie",
    metrica            AS "Métrica",
    valor              AS "Valor",
    valor_num          AS "Valor_num",
    valor_prop         AS "Valor_prop"
FROM fact_tx_rendimento;

