"""DataClient: read/write managed Delta tables using names from Governance."""

__all__ = ["DataClient"]


class DataClient:
    """Reads/writes managed Delta tables using names from Governance.

    The catalog is assumed to already exist (created once by the project
    owner). This client only creates the schema if missing.
    """

    _VALID_MODES = ("append", "overwrite")

    def __init__(self, spark, governance):
        self.spark = spark
        self.governance = governance

    def write_table(self, df, table_name, mode="overwrite", partition_cols=None):
        """Validate the name, ensure the schema exists, and write a managed
        Delta table. Returns the FQN it wrote to."""
        if mode not in self._VALID_MODES:
            raise ValueError(f"mode must be one of {self._VALID_MODES}, got: {mode!r}")

        fqn = self.governance.fqn(table_name)
        catalog = self.governance.catalog_name()
        schema = self.governance.schema_name()

        self.spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{catalog}`.`{schema}`")

        writer = df.write.format("delta").mode(mode)
        if partition_cols:
            writer = writer.partitionBy(*partition_cols)
        writer.saveAsTable(fqn)
        return fqn

    def read_table(self, table_name, filters=None):
        """Read a table by its short name, resolved to the project's FQN.

        Optionally apply ``filters`` to read only part of the table. When the
        filter targets a partition column (e.g. ``rate_date``), Spark/Delta
        prunes partitions at the file level, so an incremental read scans only
        the partitions it needs.

        ``filters`` accepts:
          - a SQL string expression:
                read_table("daily", "rate_date >= '2026-06-01'")
          - a dict of column -> value (equality, AND-combined):
                read_table("daily", {"rate_date": "2026-06-17"})
          - a list/tuple of conditions (strings or Columns, AND-combined):
                read_table("daily", ["rate_date >= '2026-06-01'", "symbol = 'BTCUSDT'"])
          - a Spark Column expression.

        Returns the (optionally filtered) DataFrame.
        """
        df = self.spark.read.table(self.governance.fqn(table_name))
        if filters is None:
            return df

        if isinstance(filters, dict):
            for col, value in filters.items():
                df = df.filter(df[col] == value)
        elif isinstance(filters, (list, tuple)):
            for condition in filters:
                df = df.filter(condition)
        else:
            df = df.filter(filters)
        return df
