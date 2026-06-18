"""Smoke tests for naming governance — no Spark required."""

import pytest

import zordon
from zordon import Governance, GovernanceError


def _gov(**overrides):
    base = dict(
        prefix="proj", country="br", region="sa", environment="dev",
        layer="bronze", domain="binance", subdomain="ohlcv",
    )
    base.update(overrides)
    return Governance(**base)


def test_catalog_name():
    assert _gov().catalog_name() == "proj_uc_br_sa_dev"


def test_bronze_schema_is_source_context():
    assert _gov(layer="bronze", domain="binance", subdomain="ohlcv").schema_name() \
        == "bronze_binance_ohlcv"


def test_silver_schema_is_conformed_context():
    assert _gov(layer="silver", domain="market", subdomain="tickers").schema_name() \
        == "silver_market_tickers"


def test_gold_schema_includes_data_product():
    gov = _gov(layer="gold", domain="finance", subdomain="investments",
               data_product="market_analysis")
    assert gov.schema_name() == "gold_finance_investments_market_analysis"


def test_fqn():
    assert _gov().fqn("daily") == "proj_uc_br_sa_dev.bronze_binance_ohlcv.daily"


@pytest.mark.parametrize("overrides", [
    {"layer": "raw"},                                   # bad layer
    {"country": "de"},                                  # bad country
    {"layer": "silver", "domain": "binance"},           # source domain in silver
    {"layer": "bronze", "domain": "market"},            # conformed domain in bronze
    {"domain": "binance", "subdomain": "fear_greed"},   # wrong subdomain for domain
    {"prefix": "Proj"},                                 # not snake_case
    {"prefix": "select"},                               # reserved word
])
def test_invalid_inputs_raise(overrides):
    with pytest.raises(GovernanceError):
        _gov(**overrides)


def test_gold_requires_data_product():
    with pytest.raises(GovernanceError):
        _gov(layer="gold", domain="finance", subdomain="investments")


def test_non_gold_forbids_data_product():
    with pytest.raises(GovernanceError):
        _gov(layer="bronze", domain="binance", subdomain="ohlcv",
             data_product="market_analysis")


def test_version_exposed():
    assert isinstance(zordon.__version__, str)
