"""Tests for DataClient using fakes — no real Spark session required."""

import sys
import types

import pytest

from zordon import Governance, DataClient


class FakeColumn:
    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return ("eq", self.name, other)


class FakeWriter:
    def __init__(self, df):
        self.df = df

    def format(self, fmt):
        self.df.write_calls.append(("format", fmt))
        return self

    def mode(self, mode):
        self.df.write_calls.append(("mode", mode))
        return self

    def option(self, key, value):
        self.df.write_calls.append(("option", key, value))
        return self

    def partitionBy(self, *cols):
        self.df.write_calls.append(("partitionBy", cols))
        return self

    def saveAsTable(self, fqn):
        self.df.write_calls.append(("saveAsTable", fqn))


class FakeDataFrame:
    def __init__(self):
        self.applied = []
        self.write_calls = []
        self.alias_name = None

    def __getitem__(self, key):
        return FakeColumn(key)

    def filter(self, condition):
        self.applied.append(condition)
        return self

    @property
    def write(self):
        return FakeWriter(self)

    def alias(self, name):
        self.alias_name = name
        return self


class FakeReader:
    def __init__(self):
        self.last_fqn = None

    def table(self, fqn):
        self.last_fqn = fqn
        return FakeDataFrame()


class FakeCatalog:
    def __init__(self, existing=()):
        self.existing = set(existing)

    def tableExists(self, fqn):
        return fqn in self.existing


class FakeSpark:
    def __init__(self, existing_tables=()):
        self.read = FakeReader()
        self.sql_calls = []
        self.catalog = FakeCatalog(existing_tables)

    def sql(self, statement):
        self.sql_calls.append(statement)


def _client(existing_tables=()):
    gov = Governance(
        country="br", region="sa", environment="dev",
        layer="bronze", domain="binance", subdomain="ohlcv",
    )
    return DataClient(FakeSpark(existing_tables), gov)


@pytest.fixture
def client():
    return _client()


# --- read_table -------------------------------------------------------------

def test_read_table_no_filter(client):
    df = client.read_table("daily")
    assert df.applied == []
    assert client.spark.read.last_fqn == "uc_br_sa_dev.bronze_binance_ohlcv.daily"


def test_read_table_string_filter(client):
    df = client.read_table("daily", "rate_date >= '2026-06-01'")
    assert df.applied == ["rate_date >= '2026-06-01'"]


def test_read_table_dict_filter(client):
    df = client.read_table("daily", {"rate_date": "2026-06-17", "symbol": "BTCUSDT"})
    assert df.applied == [("eq", "rate_date", "2026-06-17"), ("eq", "symbol", "BTCUSDT")]


def test_read_table_list_filter(client):
    df = client.read_table("daily", ["rate_date >= '2026-06-01'", "x = 1"])
    assert df.applied == ["rate_date >= '2026-06-01'", "x = 1"]


# --- write_table ------------------------------------------------------------

def test_write_table_rejects_bad_mode(client):
    with pytest.raises(ValueError):
        client.write_table(object(), "daily", mode="merge")


def test_write_table_creates_schema_and_saves(client):
    df = FakeDataFrame()
    fqn = client.write_table(df, "daily", mode="overwrite", partition_cols=["rate_date"])
    assert fqn == "uc_br_sa_dev.bronze_binance_ohlcv.daily"
    assert client.spark.sql_calls == [
        "CREATE SCHEMA IF NOT EXISTS `uc_br_sa_dev`.`bronze_binance_ohlcv`"
    ]
    assert ("saveAsTable", fqn) in df.write_calls
    assert ("partitionBy", ("rate_date",)) in df.write_calls
    # no dynamic partition overwrite unless asked for
    assert ("option", "partitionOverwriteMode", "dynamic") not in df.write_calls


def test_write_table_dynamic_partition_overwrite(client):
    df = FakeDataFrame()
    client.write_table(df, "daily", mode="overwrite", partition_cols=["rate_date"],
                       dynamic_partition_overwrite=True)
    assert ("option", "partitionOverwriteMode", "dynamic") in df.write_calls


def test_dynamic_partition_overwrite_rejected_with_append(client):
    with pytest.raises(ValueError):
        client.write_table(FakeDataFrame(), "daily", mode="append",
                           dynamic_partition_overwrite=True)


# --- upsert_table -----------------------------------------------------------

def test_upsert_rejects_empty_merge_keys(client):
    with pytest.raises(ValueError):
        client.upsert_table(FakeDataFrame(), "daily", merge_keys=[])


def test_upsert_rejects_unsafe_merge_key(client):
    with pytest.raises(ValueError):
        client.upsert_table(FakeDataFrame(), "daily", merge_keys=["symbol; drop table x"])


def test_upsert_creates_table_when_missing(client):
    df = FakeDataFrame()
    fqn = client.upsert_table(df, "daily", merge_keys="symbol", partition_cols=["rate_date"])
    assert fqn == "uc_br_sa_dev.bronze_binance_ohlcv.daily"
    # table did not exist -> created via a plain overwrite write
    assert ("saveAsTable", fqn) in df.write_calls
    assert ("partitionBy", ("rate_date",)) in df.write_calls


def test_upsert_merges_when_table_exists(monkeypatch):
    fqn = "uc_br_sa_dev.bronze_binance_ohlcv.daily"
    client = _client(existing_tables=[fqn])

    calls = {}

    class FakeMergeBuilder:
        def whenMatchedUpdateAll(self):
            calls["matched"] = True
            return self

        def whenNotMatchedInsertAll(self):
            calls["not_matched"] = True
            return self

        def execute(self):
            calls["executed"] = True

    class FakeDeltaTarget:
        def alias(self, name):
            calls["target_alias"] = name
            return self

        def merge(self, source, condition):
            calls["source_alias"] = source.alias_name
            calls["condition"] = condition
            return FakeMergeBuilder()

    class FakeDeltaTable:
        @staticmethod
        def forName(spark, name):
            calls["forName"] = name
            return FakeDeltaTarget()

    fake_module = types.ModuleType("delta.tables")
    fake_module.DeltaTable = FakeDeltaTable
    monkeypatch.setitem(sys.modules, "delta", types.ModuleType("delta"))
    monkeypatch.setitem(sys.modules, "delta.tables", fake_module)

    df = FakeDataFrame()
    result = client.upsert_table(df, "daily", merge_keys=["symbol", "rate_date"])

    assert result == fqn
    assert calls["forName"] == fqn
    assert calls["condition"] == "t.symbol = s.symbol AND t.rate_date = s.rate_date"
    assert calls["target_alias"] == "t"
    assert calls["source_alias"] == "s"
    assert calls["matched"] and calls["not_matched"] and calls["executed"]
    # no plain saveAsTable on the merge path
    assert df.write_calls == []
