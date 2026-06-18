"""Project: a factory that holds the catalog-level parts and builds clients.

The catalog parts (country / region / environment) are the same for every
schema in a project, while ``layer`` / ``domain`` / ``subdomain`` /
``data_product`` change per table. ``Project`` captures the constant parts once
so a notebook that reads several silver schemas and writes several gold schemas
does not repeat them.
"""

from .governance import Governance
from .client import DataClient

__all__ = ["Project"]


class Project:
    """Holds the constant catalog parts and builds per-schema objects.

    Example::

        proj = zordon.Project(spark, country="br", region="sa", environment="dev")

        silver = proj.client(layer="silver", domain="market", subdomain="ohlcv")
        gold   = proj.client(layer="gold", domain="finance",
                             subdomain="investments", data_product="market_analysis")

        df = silver.read_table("daily")
        gold.write_table(fact, "fact_ohlcv")
        gold.write_table(dim,  "dim_symbol")   # same schema -> reuse the client
    """

    def __init__(self, spark, country, region, environment):
        self.spark = spark
        self.country = country
        self.region = region
        self.environment = environment

    def governance(self, layer, domain, subdomain, data_product=None):
        """Build a validated :class:`Governance` for one schema, reusing the
        project's catalog parts. Raises ``GovernanceError`` on invalid parts."""
        return Governance(
            country=self.country,
            region=self.region,
            environment=self.environment,
            layer=layer,
            domain=domain,
            subdomain=subdomain,
            data_product=data_product,
        )

    def client(self, layer, domain, subdomain, data_product=None):
        """Build a :class:`DataClient` bound to one schema (read/write tables
        there). Validates the schema parts up front."""
        gov = self.governance(layer, domain, subdomain, data_product)
        return DataClient(self.spark, gov)
