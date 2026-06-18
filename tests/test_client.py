"""Tests for DataClient using fakes — no real Spark session required."""

import pytest

from zordon import Governance, DataClient


class FakeColumn:
    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return ("eq", self.name, other)


class FakeDataFrame:
    def __init__(self):
        self.applied = []

    def __getitem__(self, key):
        return FakeColumn(key)

    def filter(self, condition):
        self.applied.append(condition)
        return self


class FakeReader:
    def __init__(self):
        self.last_fqn = None

    def table(self, fqn):
        self.last_fqn = fqn
        return FakeDataFrame()


class FakeSpark:
    def __init__(self):
        self.read = FakeReader()
        self.sql_calls = []

    def sql(self, statement):
        self.sql_calls.append(statement)


@pytest.fixture
def client():
    gov = Governance(
        prefix="proj", country="br", region="sa", environment="dev",
        layer="bronze", domain="binance", subdomain="ohlcv",
    )
    return DataClient(FakeSpark(), gov)


def test_read_table_no_filter(client):
    df = client.read_table("daily")
    assert df.applied == []
    assert client.spark.read.last_fqn == "proj_uc_br_sa_dev.bronze_binance_ohlcv.daily"


def test_read_table_string_filter(client):
    df = client.read_table("daily", "rate_date >= '2026-06-01'")
    assert df.applied == ["rate_date >= '2026-06-01'"]


def test_read_table_dict_filter(client):
    df = client.read_table("daily", {"rate_date": "2026-06-17", "symbol": "BTCUSDT"})
    assert df.applied == [("eq", "rate_date", "2026-06-17"), ("eq", "symbol", "BTCUSDT")]


def test_read_table_list_filter(client):
    df = client.read_table("daily", ["rate_date >= '2026-06-01'", "x = 1"])
    assert df.applied == ["rate_date >= '2026-06-01'", "x = 1"]


def test_write_table_rejects_bad_mode(client):
    with pytest.raises(ValueError):
        client.write_table(object(), "daily", mode="merge")
