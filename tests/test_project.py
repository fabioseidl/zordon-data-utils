"""Tests for the Project factory — no Spark required."""

import pytest

import zordon
from zordon import Project, DataClient, Governance, GovernanceError


class FakeSpark:
    pass


@pytest.fixture
def proj():
    return Project(FakeSpark(), country="br", region="sa", environment="dev")


def test_governance_reuses_catalog_parts(proj):
    gov = proj.governance(layer="silver", domain="market", subdomain="ohlcv")
    assert isinstance(gov, Governance)
    assert gov.catalog_name() == "uc_sa_br_dev"
    assert gov.schema_name() == "silver_market_ohlcv"


def test_client_is_bound_to_schema(proj):
    gold = proj.client(layer="gold", domain="finance", subdomain="investments",
                       data_product="market_analysis")
    assert isinstance(gold, DataClient)
    assert gold.spark is proj.spark
    assert gold.governance.schema_name() == "gold_finance_investments_market_analysis"


def test_clients_for_different_schemas_are_independent(proj):
    silver = proj.client(layer="silver", domain="market", subdomain="ohlcv")
    gold = proj.client(layer="gold", domain="finance", subdomain="investments",
                       data_product="market_analysis")
    assert silver.governance.fqn("daily") == "uc_sa_br_dev.silver_market_ohlcv.daily"
    assert gold.governance.fqn("fact_ohlcv") == \
        "uc_sa_br_dev.gold_finance_investments_market_analysis.fact_ohlcv"


def test_invalid_schema_parts_raise(proj):
    # gold requires a data_product
    with pytest.raises(GovernanceError):
        proj.client(layer="gold", domain="finance", subdomain="investments")
    # source domain is not valid in silver
    with pytest.raises(GovernanceError):
        proj.governance(layer="silver", domain="binance", subdomain="ohlcv")


def test_project_is_exported():
    assert "Project" in zordon.__all__
