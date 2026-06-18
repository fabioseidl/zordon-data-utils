"""Tests for identifier naming validation (zordon.naming)."""

import pytest

import zordon
from zordon import GovernanceError, validate_name, is_valid_name, name_violation


# --- the spec's test-case mapping -------------------------------------------

@pytest.mark.parametrize("name", [
    "fact_sales",
    "dim_symbol",
    "silver_market_ohlcv",
    "market_analysis",
    "daily",
])
def test_approved_names(name):
    assert is_valid_name(name)
    assert validate_name(name) is True


@pytest.mark.parametrize("name, tier", [
    ("fact_sales_2026", "governance"),  # ends with a number
    ("customers_v2", "governance"),     # manual version indicator
    ("suppliers_old", "governance"),    # forbidden suffix _old
    ("test_users", "governance"),       # environment term (prefix)
    ("select", "reserved"),             # SQL reserved word
    ("sys_reg_table", "reserved"),      # reserved prefix sys
    ("table.name", "native"),           # native forbidden char '.'
])
def test_rejected_names(name, tier):
    assert not is_valid_name(name)
    assert name_violation(name)[0] == tier
    with pytest.raises(GovernanceError):
        validate_name(name)


# --- tier coverage ----------------------------------------------------------

def test_native_length_limit():
    assert is_valid_name("a" + "b" * 254)            # 255 chars, ok
    assert not is_valid_name("a" + "b" * 255)        # 256 chars, too long
    assert name_violation("a" * 256)[0] == "native"


@pytest.mark.parametrize("name", ["table name", "a/b", "a\x00b", "a\tb"])
def test_native_forbidden_characters(name):
    assert name_violation(name)[0] == "native"


def test_empty_and_non_string():
    assert not is_valid_name("")
    assert not is_valid_name(None)


@pytest.mark.parametrize("name", ["Fact", "fact-sales", "1fact"])
def test_format_tier(name):
    # uppercase, hyphen, leading digit -> format tier
    assert name_violation(name)[0] == "format"


def test_leading_underscore_is_reserved():
    assert name_violation("_metadata")[0] == "reserved"


@pytest.mark.parametrize("name", ["sys_x", "databricks_x"])
def test_reserved_prefixes(name):
    assert name_violation(name)[0] == "reserved"


@pytest.mark.parametrize("name", ["join", "union", "default", "true", "false", "select"])
def test_reserved_words(name):
    assert name_violation(name)[0] == "reserved"


@pytest.mark.parametrize("name", [
    "users_old", "users_new", "data_backup", "data_bkp",
    "stage_temp", "stage_tmp", "report_final",
])
def test_governance_versioning_suffixes(name):
    assert name_violation(name)[0] == "governance"


@pytest.mark.parametrize("name", [
    "test_users", "users_test", "dev_metrics", "metrics_prod", "sandbox_x",
])
def test_governance_environment_terms(name):
    assert name_violation(name)[0] == "governance"


@pytest.mark.parametrize("name", ["table1", "table_1", "v1", "top10"])
def test_governance_trailing_numbers(name):
    assert name_violation(name)[0] == "governance"


# --- integration with Governance / fqn --------------------------------------

def _gov(**over):
    base = dict(country="br", region="sa", environment="dev",
                layer="gold", domain="finance", subdomain="investments",
                data_product="market_analysis")
    base.update(over)
    return zordon.Governance(**base)


def test_governance_rejects_bad_data_product():
    with pytest.raises(GovernanceError):
        _gov(data_product="market_v2")


def test_fqn_rejects_bad_table_name():
    with pytest.raises(GovernanceError):
        _gov().fqn("fact_sales_2026")


def test_fqn_accepts_clean_table_name():
    assert _gov().fqn("fact_ohlcv").endswith(".fact_ohlcv")
