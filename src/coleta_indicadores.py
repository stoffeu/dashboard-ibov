
import pandas as pd
import yfinance as yf
from sqlalchemy import text

from db import EMPRESAS, aplicar_schema, get_engine, popular_dim_empresa

ANOS_DESEJADOS = {2023, 2024, 2025, 2026}


def preco_fim_de_ano(engine, ticker: str, ano: int):
    """Último preço de fechamento registrado no ano (ou None)."""
    sql = text(
        """
        SELECT fechamento
        FROM fato_cotacoes
        WHERE ticker = :ticker AND ano = :ano
        ORDER BY data DESC
        LIMIT 1
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"ticker": ticker, "ano": ano}).fetchone()
    return float(row[0]) if row else None


def preco_medio_no_ano(engine, ticker: str, ano: int):
    sql = text(
        "SELECT AVG(fechamento) FROM fato_cotacoes WHERE ticker = :ticker AND ano = :ano"
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"ticker": ticker, "ano": ano}).fetchone()
    return float(row[0]) if row and row[0] else None


def calcular_indicadores_empresa(engine, ticker: str, ticker_yahoo: str) -> list[dict]:
    print(f"Processando indicadores de {ticker} ({ticker_yahoo})...")
    ativo = yf.Ticker(ticker_yahoo)

    demonstrativo_resultado = ativo.financials       
    balanco = ativo.balance_sheet
    dividendos = ativo.dividends                     
    info = ativo.info or {}
    acoes_em_circulacao = info.get("sharesOutstanding")

    resultados = []

    if demonstrativo_resultado is None or demonstrativo_resultado.empty:
        print(f"  Aviso: sem demonstrativos financeiros para {ticker}.")
        return resultados

    receitas_por_ano = {}

    for coluna in demonstrativo_resultado.columns:
        ano = coluna.year
        if ano not in ANOS_DESEJADOS:
            continue

        try:
            lucro_liquido = demonstrativo_resultado.loc["Net Income", coluna]
            receita = demonstrativo_resultado.loc["Total Revenue", coluna]
        except KeyError:
            continue

        receitas_por_ano[ano] = receita

        patrimonio_liquido = None
        ativo_total = None
        if balanco is not None and coluna in balanco.columns:
            for chave in ["Stockholders Equity", "Total Stockholder Equity", "Common Stock Equity"]:
                if chave in balanco.index:
                    patrimonio_liquido = balanco.loc[chave, coluna]
                    break
            if "Total Assets" in balanco.index:
                ativo_total = balanco.loc["Total Assets", coluna]

        margem_liquida = (lucro_liquido / receita) if receita else None
        roe = (lucro_liquido / patrimonio_liquido) if patrimonio_liquido else None
        roa = (lucro_liquido / ativo_total) if ativo_total else None

        preco_referencia = preco_fim_de_ano(engine, ticker, ano)
        preco_medio = preco_medio_no_ano(engine, ticker, ano)

        p_l = p_vp = dividend_yield = None
        if acoes_em_circulacao:
            eps_aprox = lucro_liquido / acoes_em_circulacao
            if preco_referencia and eps_aprox:
                p_l = preco_referencia / eps_aprox
            if patrimonio_liquido:
                vpa_aprox = patrimonio_liquido / acoes_em_circulacao
                if preco_referencia and vpa_aprox:
                    p_vp = preco_referencia / vpa_aprox

        if dividendos is not None and not dividendos.empty and preco_medio:
            dividendos_do_ano = dividendos[dividendos.index.year == ano].sum()
            if dividendos_do_ano and preco_medio:
                dividend_yield = float(dividendos_do_ano) / preco_medio

        resultados.append(
            {
                "ticker": ticker,
                "ano": ano,
                "p_l": p_l,
                "p_vp": p_vp,
                "roe": roe,
                "roa": roa,
                "dividend_yield": dividend_yield,
                "margem_liquida": margem_liquida,
                "crescimento_receita": None,  # preenchido depois (precisa do ano anterior)
            }
        )

    # crescimento de receita ano contra ano
    for linha in resultados:
        ano_anterior = linha["ano"] - 1
        receita_atual = receitas_por_ano.get(linha["ano"])
        receita_anterior = receitas_por_ano.get(ano_anterior)
        if receita_atual is not None and receita_anterior:
            linha["crescimento_receita"] = (receita_atual - receita_anterior) / receita_anterior

    return resultados


def _sanitizar(valor):
    """Converte numpy.float64/NaN para tipos nativos do Python que o psycopg2 entende.

    Atenção: numpy.float64 é subclasse de float, então checar isinstance(x, float)
    NÃO é suficiente para detectá-lo — por isso chamamos .item() primeiro sempre
    que o valor tiver esse método (é como se "descasca" o tipo numpy).
    """
    if valor is None:
        return None
    if isinstance(valor, str):
        return valor
    if hasattr(valor, "item"):  # numpy.float64, numpy.int64, numpy.bool_, etc.
        valor = valor.item()
    if isinstance(valor, float) and pd.isna(valor):
        return None
    return valor


def carregar_no_postgres(registros: list[dict], engine):
    if not registros:
        print("Nenhum indicador para carregar.")
        return

    registros = [{chave: _sanitizar(valor) for chave, valor in linha.items()} for linha in registros]

    sql_upsert = text(
        """
        INSERT INTO fato_indicadores_anuais
            (ticker, ano, p_l, p_vp, roe, roa, dividend_yield, margem_liquida, crescimento_receita)
        VALUES
            (:ticker, :ano, :p_l, :p_vp, :roe, :roa, :dividend_yield, :margem_liquida, :crescimento_receita)
        ON CONFLICT (ticker, ano) DO UPDATE SET
            p_l = EXCLUDED.p_l,
            p_vp = EXCLUDED.p_vp,
            roe = EXCLUDED.roe,
            roa = EXCLUDED.roa,
            dividend_yield = EXCLUDED.dividend_yield,
            margem_liquida = EXCLUDED.margem_liquida,
            crescimento_receita = EXCLUDED.crescimento_receita,
            data_coleta = NOW()
        """
    )
    with engine.begin() as conn:
        conn.execute(sql_upsert, registros)

    print(f"{len(registros)} registros de indicadores inseridos/atualizados.")


def main():
    engine = get_engine()
    aplicar_schema(engine)
    popular_dim_empresa(engine)

    todos_registros = []
    for ticker, _, _, ticker_yahoo in EMPRESAS:
        todos_registros.extend(calcular_indicadores_empresa(engine, ticker, ticker_yahoo))

    carregar_no_postgres(todos_registros, engine)


if __name__ == "__main__":
    main()
