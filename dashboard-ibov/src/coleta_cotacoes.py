
import datetime as dt

import pandas as pd
import yfinance as yf
from sqlalchemy import text

from db import EMPRESAS, aplicar_schema, get_engine, popular_dim_empresa

DATA_INICIO = "2023-01-01"
DATA_FIM = dt.date.today().strftime("%Y-%m-%d")  


def baixar_cotacoes(tickers_yahoo: list[str]) -> pd.DataFrame:
    print(f"Baixando cotações de {DATA_INICIO} até {DATA_FIM} para: {tickers_yahoo}")
    df = yf.download(
        tickers_yahoo,
        start=DATA_INICIO,
        end=DATA_FIM,
        interval="1d",
        auto_adjust=False, 
        group_by="ticker",
        threads=True,
    )

    registros = []
    for ticker_yahoo in tickers_yahoo:
        sub = df[ticker_yahoo].copy()
        sub = sub.dropna(how="all")
        sub.reset_index(inplace=True)
        sub["ticker_yahoo"] = ticker_yahoo
        registros.append(sub)

    df_final = pd.concat(registros, ignore_index=True)
    df_final.rename(
        columns={
            "Date": "data",
            "Open": "abertura",
            "High": "maxima",
            "Low": "minima",
            "Close": "fechamento",
            "Adj Close": "fechamento_ajustado",
            "Volume": "volume",
        },
        inplace=True,
    )
    df_final.dropna(subset=["fechamento"], inplace=True)
    return df_final


def carregar_no_postgres(df: pd.DataFrame, engine):
    mapa_ticker = {nome_yahoo: ticker for ticker, _, _, nome_yahoo in EMPRESAS}
    df["ticker"] = df["ticker_yahoo"].map(mapa_ticker)

    colunas = [
        "ticker",
        "data",
        "abertura",
        "maxima",
        "minima",
        "fechamento",
        "fechamento_ajustado",
        "volume",
    ]
    df = df[colunas]

    sql_upsert = text(
        """
        INSERT INTO fato_cotacoes
            (ticker, data, abertura, maxima, minima, fechamento, fechamento_ajustado, volume)
        VALUES
            (:ticker, :data, :abertura, :maxima, :minima, :fechamento, :fechamento_ajustado, :volume)
        ON CONFLICT (ticker, data) DO UPDATE SET
            abertura = EXCLUDED.abertura,
            maxima = EXCLUDED.maxima,
            minima = EXCLUDED.minima,
            fechamento = EXCLUDED.fechamento,
            fechamento_ajustado = EXCLUDED.fechamento_ajustado,
            volume = EXCLUDED.volume
        """
    )

    registros = df.to_dict(orient="records")
    with engine.begin() as conn:
        for i in range(0, len(registros), 1000):
            lote = registros[i : i + 1000]
            conn.execute(sql_upsert, lote)

    print(f"{len(registros)} registros de cotações inseridos/atualizados.")


def main():
    engine = get_engine()
    aplicar_schema(engine)
    popular_dim_empresa(engine)

    tickers_yahoo = [t[3] for t in EMPRESAS]
    df = baixar_cotacoes(tickers_yahoo)
    carregar_no_postgres(df, engine)


if __name__ == "__main__":
    main()
