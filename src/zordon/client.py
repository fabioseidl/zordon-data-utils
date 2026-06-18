"""DataClient: read/write managed Delta tables using names from Governance."""

import re

__all__ = ["DataClient"]

# simple SQL identifier: used to keep merge-key column names from being able to
# inject anything into the MERGE condition.
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class DataClient:
    """Reads/writes managed Delta tables using names from Governance.

    The catalog is assumed to already exist (created once by the project
    owner). This client only creates the schema if missing.
    """

    _VALID_MODES = ("append", "overwrite")

    def __init__(self, spark, governance):
        self.spark = spark
        self.governance = governance

    def _ensure_schema(self):
        """Run CREATE SCHEMA IF NOT EXISTS for the governed schema."""
        catalog = self.governance.catalog_name()
        schema = self.governance.schema_name()
        self.spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{catalog}`.`{schema}`")

    def write_table(self, df, table_name, mode="overwrite", partition_cols=None,
                    dynamic_partition_overwrite=False):
        """Validate the name, ensure the schema exists, and write a managed
        Delta table. Returns the FQN it wrote to.

        ``dynamic_partition_overwrite=True`` enables dynamic partition overwrite
        (``partitionOverwriteMode=dynamic``): an ``"overwrite"`` then replaces
        only the partitions present in ``df`` instead of the whole table — handy
        for reprocessing a single ``rate_date`` without touching the others. It
        is only valid with ``mode="overwrite"``.
        """
        if mode not in self._VALID_MODES:
            raise ValueError(f"mode must be one of {self._VALID_MODES}, got: {mode!r}")
        if dynamic_partition_overwrite and mode != "overwrite":
            raise ValueError(
                "dynamic_partition_overwrite is only valid with mode='overwrite'"
            )

        fqn = self.governance.fqn(table_name)
        self._ensure_schema()

        writer = df.write.format("delta").mode(mode)
        if dynamic_partition_overwrite:
            writer = writer.option("partitionOverwriteMode", "dynamic")
        if partition_cols:
            writer = writer.partitionBy(*partition_cols)
        writer.saveAsTable(fqn)
        return fqn

    def upsert_table(self, df, table_name, merge_keys, partition_cols=None):
        """Upsert (MERGE) ``df`` into a managed Delta table.

        Rows whose ``merge_keys`` match an existing row are updated; rows with
        no match are inserted. The table is created on first use (so the first
        call behaves like ``write_table``), then subsequent calls run a Delta
        ``MERGE``. Returns the FQN it wrote to.

        ``merge_keys`` is the column (str) or columns (list of str) that
        uniquely identify a row, e.g. ``["symbol", "rate_date"]`` for OHLCV.

        ``partition_cols`` is only used when the table is created on the first
        call; it is ignored once the table exists.
        """
        if isinstance(merge_keys, str):
            merge_keys = [merge_keys]
        if not merge_keys:
            raise ValueError("merge_keys must be a non-empty column name or list of names")
        for key in merge_keys:
            if not isinstance(key, str) or not _IDENTIFIER.match(key):
                raise ValueError(f"invalid merge key: {key!r}")

        fqn = self.governance.fqn(table_name)
        self._ensure_schema()

        # First call: no table yet, so create it with a plain write. This makes
        # upsert_table idempotent to run from scratch.
        if not self.spark.catalog.tableExists(fqn):
            writer = df.write.format("delta").mode("overwrite")
            if partition_cols:
                writer = writer.partitionBy(*partition_cols)
            writer.saveAsTable(fqn)
            return fqn

        # Existing table: MERGE update-or-insert on the merge keys.
        from delta.tables import DeltaTable  # lazy: only needed on Databricks

        condition = " AND ".join(f"t.{key} = s.{key}" for key in merge_keys)
        (
            DeltaTable.forName(self.spark, fqn)
            .alias("t")
            .merge(df.alias("s"), condition)
            .whenMatchedUpdateAll()
            .whenNotMatchedInsertAll()
            .execute()
        )
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
