-- ═══════════════════════════════════════════════════════════════
-- DDL do banco (PostgreSQL) — Modelo Estrela para BI
-- Projeto: educacaoPainel_V2
-- ═══════════════════════════════════════════════════════════════

-- ── DIMENSÕES ──────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS dim_tempo (
    sk_tempo  SERIAL PRIMARY KEY,
    ano       INT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dim_localizacao (
    sk_localizacao  SERIAL PRIMARY KEY,
    cod_localizacao TEXT NOT NULL UNIQUE,
    descricao       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_dependencia (
    sk_dependencia  SERIAL PRIMARY KEY,
    cod_dependencia TEXT NOT NULL UNIQUE,
    descricao       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_grupo_medida (
    sk_grupo_medida SERIAL PRIMARY KEY,
    grupo           TEXT NOT NULL,
    etapa           TEXT NOT NULL,
    UNIQUE(grupo, etapa)
);

CREATE TABLE IF NOT EXISTS dim_grupo_infra (
    sk_grupo_infra SERIAL PRIMARY KEY,
    grupo_infra    TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dim_categoria_indigena (
    sk_categoria_indigena SERIAL PRIMARY KEY,
    categoria             TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dim_metrica (
    sk_metrica SERIAL PRIMARY KEY,
    metrica    TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dim_tipo_receita (
    sk_tipo_receita SERIAL PRIMARY KEY,
    cod_receita     TEXT NOT NULL UNIQUE,
    descricao       TEXT,
    categoria       TEXT
);

CREATE TABLE IF NOT EXISTS dim_tipo_despesa (
    sk_tipo_despesa SERIAL PRIMARY KEY,
    cod_despesa     TEXT NOT NULL UNIQUE,
    descricao       TEXT,
    categoria       TEXT
);

CREATE TABLE IF NOT EXISTS dim_municipio (
    cod_municipio TEXT PRIMARY KEY,
    nome          TEXT,
    uf            TEXT,
    regiao        TEXT
);

CREATE TABLE IF NOT EXISTS dim_escola (
    cod_escola     TEXT PRIMARY KEY,
    nome           TEXT,
    cod_municipio  TEXT REFERENCES dim_municipio(cod_municipio),
    sk_dependencia INT REFERENCES dim_dependencia(sk_dependencia),
    sk_localizacao INT REFERENCES dim_localizacao(sk_localizacao)
);

CREATE INDEX IF NOT EXISTS ix_dim_escola_municipio ON dim_escola(cod_municipio);
CREATE INDEX IF NOT EXISTS ix_dim_escola_depend   ON dim_escola(sk_dependencia);
CREATE INDEX IF NOT EXISTS ix_dim_escola_local    ON dim_escola(sk_localizacao);

-- ── SEEDS ──────────────────────────────────────────────────────

-- Localização
INSERT INTO dim_localizacao (cod_localizacao, descricao) VALUES
    ('1', 'Urbana'), ('2', 'Rural')
ON CONFLICT (cod_localizacao) DO NOTHING;

-- Dependência
INSERT INTO dim_dependencia (cod_dependencia, descricao) VALUES
    ('1', 'Federal'), ('2', 'Estadual'), ('3', 'Municipal'), ('4', 'Privada')
ON CONFLICT (cod_dependencia) DO NOTHING;

-- Grupos de Medida (Censo)
INSERT INTO dim_grupo_medida (grupo, etapa) VALUES
    ('Matrículas', 'Educação Especial'),
    ('Matrículas', 'Ed. Infantil - Creche'),
    ('Matrículas', 'Ed. Infantil - Pré-Escola'),
    ('Matrículas', 'Ensino Fund. - Anos Iniciais'),
    ('Matrículas', 'Ensino Fund. - Anos Finais'),
    ('Matrículas', 'Ensino Médio'),
    ('Matrículas', 'EJA - Ensino Fundamental'),
    ('Matrículas', 'EJA - Ensino Médio'),
    ('Matrículas - Tempo Integral', 'Ed. Infantil - Creche'),
    ('Matrículas - Tempo Integral', 'Ed. Infantil - Pré-Escola'),
    ('Matrículas - Tempo Integral', 'Ensino Fund. - Anos Iniciais'),
    ('Matrículas - Tempo Integral', 'Ensino Fund. - Anos Finais'),
    ('Matrículas - Tempo Integral', 'Ensino Médio'),
    ('Turmas', 'Educação Especial'),
    ('Turmas', 'Ed. Infantil - Creche'),
    ('Turmas', 'Ed. Infantil - Pré-Escola'),
    ('Turmas', 'Ensino Fund. - Anos Iniciais'),
    ('Turmas', 'Ensino Fund. - Anos Finais'),
    ('Turmas', 'Ensino Médio'),
    ('Turmas', 'EJA - Ensino Fundamental'),
    ('Turmas', 'EJA - Ensino Médio'),
    ('Docentes', 'Educação Básica (Total)'),
    ('Docentes', 'Educação Especial'),
    ('Docentes', 'Ed. Infantil - Creche'),
    ('Docentes', 'Ed. Infantil - Pré-Escola'),
    ('Docentes', 'Ensino Fund. - Anos Iniciais'),
    ('Docentes', 'Ensino Fund. - Anos Finais'),
    ('Docentes', 'Ensino Médio'),
    ('Docentes', 'EJA - Ensino Fundamental'),
    ('Docentes', 'EJA - Ensino Médio'),
    ('Docentes (Estimado)', 'Educação Especial'),
    ('Docentes (Estimado)', 'Ed. Infantil - Creche'),
    ('Docentes (Estimado)', 'Ed. Infantil - Pré-Escola'),
    ('Docentes (Estimado)', 'Ensino Fund. - Anos Iniciais'),
    ('Docentes (Estimado)', 'Ensino Fund. - Anos Finais'),
    ('Docentes (Estimado)', 'Ensino Médio'),
    ('Docentes (Estimado)', 'EJA - Ensino Fundamental'),
    ('Docentes (Estimado)', 'EJA - Ensino Médio'),
    ('Escolas', 'Todas'),
    ('Matrículas Indígenas (Total)', 'Todas'),
    ('Matrículas Indígenas (Etapas)', 'Educação Especial'),
    ('Matrículas Indígenas (Etapas)', 'Ed. Infantil - Creche'),
    ('Matrículas Indígenas (Etapas)', 'Ed. Infantil - Pré-Escola'),
    ('Matrículas Indígenas (Etapas)', 'Ensino Fund. - Anos Iniciais'),
    ('Matrículas Indígenas (Etapas)', 'Ensino Fund. - Anos Finais'),
    ('Matrículas Indígenas (Etapas)', 'Ensino Médio'),
    ('Matrículas Indígenas (Etapas)', 'EJA - Ensino Fundamental'),
    ('Matrículas Indígenas (Etapas)', 'EJA - Ensino Médio'),
    ('Matrículas Indígenas (Etapas)', 'Não detalhado'),
    ('Matrículas (GERAL)', 'Educação Especial'),
    ('Matrículas (GERAL)', 'Ed. Infantil - Creche'),
    ('Matrículas (GERAL)', 'Ed. Infantil - Pré-Escola'),
    ('Matrículas (GERAL)', 'Ensino Fund. - Anos Iniciais'),
    ('Matrículas (GERAL)', 'Ensino Fund. - Anos Finais'),
    ('Matrículas (GERAL)', 'Ensino Médio'),
    ('Matrículas (GERAL)', 'EJA - Ensino Fundamental'),
    ('Matrículas (GERAL)', 'EJA - Ensino Médio')
ON CONFLICT (grupo, etapa) DO NOTHING;

-- Grupos de Infraestrutura
INSERT INTO dim_grupo_infra (grupo_infra) VALUES
    ('Água'), ('Energia'), ('Esgoto'), ('Lixo'),
    ('Internet/TIC'), ('Dependências'), ('Acessibilidade'), ('Outros')
ON CONFLICT (grupo_infra) DO NOTHING;

-- Categorias Indígenas
INSERT INTO dim_categoria_indigena (categoria) VALUES
    ('Escola Indígena'), ('Em Terra Indígena'), ('Com Língua Indígena'), ('Não indígena')
ON CONFLICT (categoria) DO NOTHING;

-- Métricas de Rendimento
INSERT INTO dim_metrica (metrica) VALUES
    ('Taxa de Aprovação'), ('Taxa de Reprovação'), ('Taxa de Abandono')
ON CONFLICT (metrica) DO NOTHING;

-- Tipos de Receita (SIOPE)
INSERT INTO dim_tipo_receita (cod_receita, descricao, categoria) VALUES
    ('RECEITA_ORCAMENTARIA', 'Receita Orçamentária', 'Receita'),
    ('RECEITA_REALIZADA', 'Receita Realizada', 'Receita'),
    ('RECEITA_PREVISTA_ATUALIZADA', 'Receita Prevista Atualizada', 'Receita'),
    ('FPM', 'Fundo de Partilha do Minas', 'Transferência'),
    ('FPE', 'Fundo de Participação dos Estados', 'Transferência'),
    ('ITR', 'Imposto Territorial Rural', 'Imposto'),
    ('ICMS', 'ICMS', 'Imposto'),
    ('IPI_EXPORTACAO', 'IPI de Exportação', 'Imposto'),
    ('CIDE', 'CIDE', 'Imposto'),
    ('FUNDEB', 'FUNDEB', 'FUNDEB'),
    ('CP_FUNDEB', 'Cota-Parte FUNDEB', 'FUNDEB'),
    ('IPVA_FUNDEB', 'IPVA para FUNDEB', 'FUNDEB'),
    ('ITCMD_FUNDEB', 'ITCMD para FUNDEB', 'FUNDEB'),
    ('TRANSMISSAO', 'Transmissão', 'Receita')
ON CONFLICT (cod_receita) DO NOTHING;

-- Tipos de Despesa (SIOPE)
INSERT INTO dim_tipo_despesa (cod_despesa, descricao, categoria) VALUES
    ('GERAL_ORCAMENTARIA', 'Despesa Orçamentária', 'Geral'),
    ('GERAL_DOTACAO_ATUALIZADA', 'Despesa Dotação Atualizada', 'Geral'),
    ('GERAL_EMPENHADA', 'Despesa Empenhada', 'Geral'),
    ('GERAL_LIQUIDADA', 'Despesa Liquidada', 'Geral'),
    ('GERAL_PAGA', 'Despesa Paga', 'Geral'),
    ('EDU_ORCAMENTARIA', 'Despesa Orçamentária Educação', 'Educação'),
    ('EDU_DOTACAO_ATUALIZADA', 'Despesa Dotação Atualizada Educação', 'Educação'),
    ('EDU_EMPENHADA', 'Despesa Empenhada Educação', 'Educação'),
    ('EDU_LIQUIDADA', 'Despesa Liquidada Educação', 'Educação'),
    ('EDU_PAGA', 'Despesa Paga Educação', 'Educação')
ON CONFLICT (cod_despesa) DO NOTHING;

-- ── TABELAS DE FATO ────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS fact_censo_medida (
    sk_tempo        INT REFERENCES dim_tempo(sk_tempo),
    cod_escola      TEXT REFERENCES dim_escola(cod_escola),
    sk_grupo_medida INT REFERENCES dim_grupo_medida(sk_grupo_medida),
    qt              INT,
    PRIMARY KEY(sk_tempo, cod_escola, sk_grupo_medida)
);

CREATE TABLE IF NOT EXISTS fact_infra_escola (
    sk_tempo       INT REFERENCES dim_tempo(sk_tempo),
    cod_escola     TEXT REFERENCES dim_escola(cod_escola),
    sk_grupo_infra INT REFERENCES dim_grupo_infra(sk_grupo_infra),
    item           TEXT,
    possui         INT,
    PRIMARY KEY(sk_tempo, cod_escola, item)
);

CREATE TABLE IF NOT EXISTS fact_indigena (
    sk_tempo              INT REFERENCES dim_tempo(sk_tempo),
    cod_escola            TEXT REFERENCES dim_escola(cod_escola),
    sk_categoria_indigena INT REFERENCES dim_categoria_indigena(sk_categoria_indigena),
    sk_grupo_medida       INT REFERENCES dim_grupo_medida(sk_grupo_medida),
    qt                    INT,
    PRIMARY KEY(sk_tempo, cod_escola, sk_categoria_indigena, sk_grupo_medida)
);

CREATE TABLE IF NOT EXISTS fact_tx_rendimento (
    sk_tempo      INT REFERENCES dim_tempo(sk_tempo),
    cod_municipio TEXT REFERENCES dim_municipio(cod_municipio),
    cod_escola    TEXT,
    sk_metrica    INT REFERENCES dim_metrica(sk_metrica),
    etapa         TEXT,
    serie         INT,
    valor         TEXT,
    valor_num     DOUBLE PRECISION,
    valor_prop    DOUBLE PRECISION,
    PRIMARY KEY(sk_tempo, cod_municipio, cod_escola, sk_metrica, etapa, serie)
);

CREATE TABLE IF NOT EXISTS fact_siope_receita (
    sk_tempo        INT REFERENCES dim_tempo(sk_tempo),
    cod_municipio   TEXT REFERENCES dim_municipio(cod_municipio),
    sk_tipo_receita INT REFERENCES dim_tipo_receita(sk_tipo_receita),
    valor           NUMERIC,
    PRIMARY KEY(sk_tempo, cod_municipio, sk_tipo_receita)
);

CREATE TABLE IF NOT EXISTS fact_siope_despesa (
    sk_tempo        INT REFERENCES dim_tempo(sk_tempo),
    cod_municipio   TEXT REFERENCES dim_municipio(cod_municipio),
    sk_tipo_despesa INT REFERENCES dim_tipo_despesa(sk_tipo_despesa),
    valor           NUMERIC,
    PRIMARY KEY(sk_tempo, cod_municipio, sk_tipo_despesa)
);

CREATE TABLE IF NOT EXISTS fact_siope_indicadores (
    sk_tempo           INT REFERENCES dim_tempo(sk_tempo),
    cod_municipio      TEXT REFERENCES dim_municipio(cod_municipio),
    populacao          NUMERIC,
    valor_pib          NUMERIC,
    valor_pib_percapto NUMERIC,
    PRIMARY KEY(sk_tempo, cod_municipio)
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

-- ── ÍNDICES ────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS ix_fact_censo_escola   ON fact_censo_medida(cod_escola);
CREATE INDEX IF NOT EXISTS ix_fact_censo_tempo    ON fact_censo_medida(sk_tempo);
CREATE INDEX IF NOT EXISTS ix_fact_infra_escola  ON fact_infra_escola(cod_escola);
CREATE INDEX IF NOT EXISTS ix_fact_indig_escola  ON fact_indigena(cod_escola);
CREATE INDEX IF NOT EXISTS ix_fact_rend_escola   ON fact_tx_rendimento(cod_escola);
CREATE INDEX IF NOT EXISTS ix_fact_rend_mun      ON fact_tx_rendimento(cod_municipio);
CREATE INDEX IF NOT EXISTS ix_fact_siope_rec_mun ON fact_siope_receita(cod_municipio);
CREATE INDEX IF NOT EXISTS ix_fact_siope_des_mun ON fact_siope_despesa(cod_municipio);
CREATE INDEX IF NOT EXISTS ix_fact_siope_ind_mun ON fact_siope_indicadores(cod_municipio);

-- ── VIEWS PARA BI ──────────────────────────────────────────────

CREATE OR REPLACE VIEW vw_fact_censo AS
SELECT
    t.ano,
    m.cod_municipio, m.nome AS nome_municipio, m.uf, m.regiao,
    e.cod_escola, e.nome AS nome_escola,
    d.descricao AS dependencia, l.descricao AS localizacao,
    gm.grupo, gm.etapa,
    f.qt
FROM fact_censo_medida f
JOIN dim_tempo t           ON f.sk_tempo = t.sk_tempo
JOIN dim_escola e          ON f.cod_escola = e.cod_escola
JOIN dim_municipio m       ON e.cod_municipio = m.cod_municipio
JOIN dim_grupo_medida gm   ON f.sk_grupo_medida = gm.sk_grupo_medida
JOIN dim_dependencia d     ON e.sk_dependencia = d.sk_dependencia
JOIN dim_localizacao l     ON e.sk_localizacao = l.sk_localizacao;

CREATE OR REPLACE VIEW vw_fact_infra AS
SELECT
    t.ano,
    m.cod_municipio, m.nome AS nome_municipio, m.uf, m.regiao,
    e.cod_escola, e.nome AS nome_escola,
    d.descricao AS dependencia, l.descricao AS localizacao,
    gi.grupo_infra, f.item, f.possui
FROM fact_infra_escola f
JOIN dim_tempo t           ON f.sk_tempo = t.sk_tempo
JOIN dim_escola e          ON f.cod_escola = e.cod_escola
JOIN dim_municipio m       ON e.cod_municipio = m.cod_municipio
JOIN dim_grupo_infra gi    ON f.sk_grupo_infra = gi.sk_grupo_infra
JOIN dim_dependencia d     ON e.sk_dependencia = d.sk_dependencia
JOIN dim_localizacao l     ON e.sk_localizacao = l.sk_localizacao;

CREATE OR REPLACE VIEW vw_fact_indigena AS
SELECT
    t.ano,
    m.cod_municipio, m.nome AS nome_municipio, m.uf, m.regiao,
    e.cod_escola, e.nome AS nome_escola,
    d.descricao AS dependencia, l.descricao AS localizacao,
    ci.categoria, gm.grupo, gm.etapa,
    f.qt
FROM fact_indigena f
JOIN dim_tempo t              ON f.sk_tempo = t.sk_tempo
JOIN dim_escola e             ON f.cod_escola = e.cod_escola
JOIN dim_municipio m          ON e.cod_municipio = m.cod_municipio
JOIN dim_categoria_indigena ci ON f.sk_categoria_indigena = ci.sk_categoria_indigena
JOIN dim_grupo_medida gm      ON f.sk_grupo_medida = gm.sk_grupo_medida
JOIN dim_dependencia d        ON e.sk_dependencia = d.sk_dependencia
JOIN dim_localizacao l        ON e.sk_localizacao = l.sk_localizacao;

CREATE OR REPLACE VIEW vw_fact_rendimento AS
SELECT
    t.ano,
    m.cod_municipio, m.nome AS nome_municipio, m.uf, m.regiao,
    f.cod_escola,
    me.metrica, f.etapa, f.serie,
    f.valor, f.valor_num, f.valor_prop
FROM fact_tx_rendimento f
JOIN dim_tempo t      ON f.sk_tempo = t.sk_tempo
JOIN dim_municipio m  ON f.cod_municipio = m.cod_municipio
JOIN dim_metrica me   ON f.sk_metrica = me.sk_metrica;

CREATE OR REPLACE VIEW vw_fact_siope_receita AS
SELECT
    t.ano,
    m.cod_municipio, m.nome AS nome_municipio, m.uf, m.regiao,
    tr.cod_receita, tr.descricao AS tipo_receita, tr.categoria AS categoria_receita,
    f.valor
FROM fact_siope_receita f
JOIN dim_tempo t         ON f.sk_tempo = t.sk_tempo
JOIN dim_municipio m     ON f.cod_municipio = m.cod_municipio
JOIN dim_tipo_receita tr ON f.sk_tipo_receita = tr.sk_tipo_receita;

CREATE OR REPLACE VIEW vw_fact_siope_despesa AS
SELECT
    t.ano,
    m.cod_municipio, m.nome AS nome_municipio, m.uf, m.regiao,
    td.cod_despesa, td.descricao AS tipo_despesa, td.categoria AS categoria_despesa,
    f.valor
FROM fact_siope_despesa f
JOIN dim_tempo t         ON f.sk_tempo = t.sk_tempo
JOIN dim_municipio m     ON f.cod_municipio = m.cod_municipio
JOIN dim_tipo_despesa td ON f.sk_tipo_despesa = td.sk_tipo_despesa;

CREATE OR REPLACE VIEW vw_fact_siope_indicadores AS
SELECT
    t.ano,
    m.cod_municipio, m.nome AS nome_municipio, m.uf, m.regiao,
    f.populacao, f.valor_pib, f.valor_pib_percapto
FROM fact_siope_indicadores f
JOIN dim_tempo t     ON f.sk_tempo = t.sk_tempo
JOIN dim_municipio m ON f.cod_municipio = m.cod_municipio;

-- ── VIEWS DE COMPATIBILIDADE (CSVs antigos) ────────────────────

CREATE OR REPLACE VIEW vw_dados_normalizados_por_etapa AS
SELECT ano, uf, cod_municipio, nome_municipio, dependencia AS tp_dependencia,
       localizacao AS tp_localizacao, cod_escola, nome_escola,
       grupo, etapa, qt
FROM vw_fact_censo;

CREATE OR REPLACE VIEW vw_infra_escola_long AS
SELECT ano, uf, cod_municipio, nome_municipio, dependencia AS tp_dependencia,
       localizacao AS tp_localizacao, cod_escola, nome_escola,
       grupo_infra AS "GrupoInfra", item AS "Item", possui AS "POSSUI"
FROM vw_fact_infra;

CREATE OR REPLACE VIEW vw_dados_indigena_normalizado AS
SELECT ano, uf, cod_municipio, nome_municipio, dependencia AS tp_dependencia,
       localizacao AS tp_localizacao, cod_escola, nome_escola,
       categoria AS "CategoriaIndigena", grupo, etapa, qt
FROM vw_fact_indigena;

CREATE OR REPLACE VIEW vw_tx_rendimento_long AS
SELECT t.ano, m.regiao AS "Região", m.uf, m.cod_municipio AS "Código do Município",
       m.nome AS "Nome do Município", r.cod_escola AS "Código da Escola",
       r.etapa AS "Etapa", r.serie AS "Serie",
       me.metrica AS "Métrica", r.valor AS "Valor",
       r.valor_num AS "Valor_num", r.valor_prop AS "Valor_prop"
FROM fact_tx_rendimento r
JOIN dim_tempo t    ON r.sk_tempo = t.sk_tempo
JOIN dim_municipio m ON r.cod_municipio = m.cod_municipio
JOIN dim_metrica me ON r.sk_metrica = me.sk_metrica;

CREATE OR REPLACE VIEW vw_siope_detalhado AS
SELECT * FROM vw_fact_siope_receita;
