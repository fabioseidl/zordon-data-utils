"""
zordon
======

Tiny helper library for a student data-engineering project on Databricks.

Its only job: make every developer working on the project in parallel follow
the SAME naming rules for Unity Catalog (catalog / schema / table), and write
managed Delta tables to those names.

Naming standard
---------------
    catalog : uc_{country}_{region}_{environment}            -> uc_br_sa_dev

    schema depends on the layer:
      bronze / silver : {layer}_{domain}_{subdomain}                  -> bronze_binance_ohlcv / silver_market_ohlcv
      gold            : {layer}_{domain}_{subdomain}_{data_product}   -> gold_finance_investments_market_analysis

    table   : {table_name}                                   -> daily
    fqn     : {catalog}.{schema}.{table_name}

Each medallion layer is organised by a different principle, so the
domain/subdomain vocabulary is layer-dependent (see ``zordon.vocabularies``):
    bronze -> by SOURCE   : domain="binance",  subdomain="ohlcv"
    silver -> by CONTEXT  : domain="market",   subdomain="ohlcv"   (sources merged)
    gold   -> by PRODUCT  : domain="finance",  subdomain="investments",
                            data_product="market_analysis"

Quick start
-----------
    import zordon

    gov = zordon.Governance(
        country="br", region="sa", environment="dev",
        layer="bronze", domain="binance", subdomain="ohlcv",
    )
    client = zordon.DataClient(spark, gov)
    client.write_table(df, "daily", mode="overwrite", partition_cols=["rate_date"])
    df = client.read_table("daily", filters="rate_date >= '2026-06-01'")

When a notebook touches several schemas (e.g. read silver, write gold), use a
Project so the catalog parts are stated once and you get a client per schema::

    proj = zordon.Project(spark, country="br", region="sa", environment="dev")
    silver = proj.client(layer="silver", domain="market", subdomain="ohlcv")
    gold   = proj.client(layer="gold", domain="finance",
                         subdomain="investments", data_product="market_analysis")
    gold.write_table(silver.read_table("daily"), "fact_ohlcv")
"""

from .errors import GovernanceError
from .governance import Governance
from .client import DataClient
from .project import Project
from .vocabularies import (
    LAYERS, COUNTRIES, ENVIRONMENTS,
    BRONZE_DOMAINS, BRONZE_SUBDOMAINS,
    SILVER_DOMAINS, SILVER_SUBDOMAINS,
    GOLD_DOMAINS, GOLD_SUBDOMAINS,
    DOMAIN_VOCAB_BY_LAYER,
)

__version__ = "1.4.0"

__all__ = [
    "Project", "Governance", "DataClient", "GovernanceError",
    "LAYERS", "COUNTRIES", "ENVIRONMENTS",
    "BRONZE_DOMAINS", "BRONZE_SUBDOMAINS",
    "SILVER_DOMAINS", "SILVER_SUBDOMAINS",
    "GOLD_DOMAINS", "GOLD_SUBDOMAINS",
    "DOMAIN_VOCAB_BY_LAYER",
    "__version__",
]
