-- ============================================================
-- Schema: Dashboard Analítico Ibovespa
-- Banco: PostgreSQL
-- ============================================================

CREATE TABLE IF NOT EXISTS dim_empresa (
    ticker          VARCHAR(10) PRIMARY KEY,   -- Ex: PETR4, VALE3
    nome            VARCHAR(120) NOT NULL,
    setor           VARCHAR(80),
    ticker_yahoo    VARCHAR(15) NOT NULL        -- Ex: PETR4.SA
);

CREATE TABLE IF NOT EXISTS fato_cotacoes (
    id                      BIGSERIAL PRIMARY KEY,
    ticker                  VARCHAR(10) NOT NULL REFERENCES dim_empresa(ticker),
    data                    DATE NOT NULL,
    abertura                NUMERIC(12,4),
    maxima                  NUMERIC(12,4),
    minima                  NUMERIC(12,4),
    fechamento              NUMERIC(12,4),
    fechamento_ajustado     NUMERIC(12,4),
    volume                  BIGINT,
    ano                     INT GENERATED ALWAYS AS (EXTRACT(YEAR FROM data)::INT) STORED,
    mes                     INT GENERATED ALWAYS AS (EXTRACT(MONTH FROM data)::INT) STORED,
    UNIQUE (ticker, data)
);

CREATE INDEX IF NOT EXISTS idx_fato_cotacoes_ticker_data ON fato_cotacoes (ticker, data);

CREATE TABLE IF NOT EXISTS fato_indicadores_anuais (
    id                      BIGSERIAL PRIMARY KEY,
    ticker                  VARCHAR(10) NOT NULL REFERENCES dim_empresa(ticker),
    ano                     INT NOT NULL,
    p_l                     NUMERIC(12,4),   -- Preço / Lucro
    p_vp                    NUMERIC(12,4),   -- Preço / Valor Patrimonial
    roe                     NUMERIC(12,6),   -- Return on Equity
    roa                     NUMERIC(12,6),   -- Return on Assets
    dividend_yield          NUMERIC(12,6),
    margem_liquida          NUMERIC(12,6),
    crescimento_receita     NUMERIC(12,6),
    data_coleta             TIMESTAMP DEFAULT NOW(),
    UNIQUE (ticker, ano)
);

CREATE INDEX IF NOT EXISTS idx_fato_indicadores_ticker_ano ON fato_indicadores_anuais (ticker, ano);
