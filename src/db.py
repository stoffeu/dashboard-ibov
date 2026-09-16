
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/ibov_dashboard",
)


def get_engine():
    return create_engine(DATABASE_URL)


def aplicar_schema(engine, caminho_schema="schema.sql"):
    """Executa o schema.sql para garantir que as tabelas existam."""
    with open(caminho_schema, "r", encoding="utf-8") as f:
        ddl = f.read()
    with engine.begin() as conn:
        for comando in ddl.split(";"):
            comando = comando.strip()
            if comando:
                conn.execute(text(comando))


EMPRESAS = [
    
    ("PETR4", "Petróleo Brasileiro S.A. - Petrobras", "Petróleo, Gás e Biocombustíveis", "PETR4.SA"),
    ("VALE3", "Vale S.A.",                              "Mineração",                       "VALE3.SA"),
    ("ITUB4", "Itaú Unibanco Holding S.A.",              "Bancos",                          "ITUB4.SA"),
    ("WEGE3", "WEG S.A.",                                "Bens Industriais",                "WEGE3.SA"),
    ("RENT3", "Localiza Rent a Car S.A.",                "Locação de Veículos",             "RENT3.SA"),
]


def popular_dim_empresa(engine):
    from sqlalchemy import text as sqltext
    with engine.begin() as conn:
        for ticker, nome, setor, ticker_yahoo in EMPRESAS:
            conn.execute(
                sqltext(
                    """
                    INSERT INTO dim_empresa (ticker, nome, setor, ticker_yahoo)
                    VALUES (:ticker, :nome, :setor, :ticker_yahoo)
                    ON CONFLICT (ticker) DO UPDATE
                    SET nome = EXCLUDED.nome, setor = EXCLUDED.setor, ticker_yahoo = EXCLUDED.ticker_yahoo
                    """
                ),
                {"ticker": ticker, "nome": nome, "setor": setor, "ticker_yahoo": ticker_yahoo},
            )
