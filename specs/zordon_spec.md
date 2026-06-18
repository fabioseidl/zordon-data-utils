# zordon — Library Specification

Version: 1.4

Status: reference / validation document

## 1. Purpose

`zordon` is a small helper library for a student data-engineering project on Databricks (PySpark). Its single objective is to make every developer working on the project in parallel follow the **same naming rules** for Unity Catalog (catalog / schema / table), and to write managed Delta tables to those names.

It is packaged as a small, dependency-light Python package under a `src` layout (`src/zordon/`). It can be used three ways: imported directly from the `src` folder (via `sys.path`), installed editable on the cluster (`pip install -e`), or built into a wheel and installed as a cluster library. See the README, section "Installing / making it importable", for the steps.

## 2. Scope

In scope (v1.4):
- Two-tier validation of naming inputs:
  - controlled vocabulary (value must exist in a fixed dictionary), and
  - free-form format (lowercase snake_case).
- Construction of catalog, schema and fully qualified names (FQN).
- Writing **managed** Delta tables to Unity Catalog (overwrite / append).
- Upserting (Delta `MERGE`) into a managed table on a set of key columns.
- Reading tables back by short name, with optional filters.

Out of scope:
- External tables / ADLS Gen2 URIs (managed tables only).
- Permissions / `GRANT`.
- `CREATE CATALOG` (catalog is assumed to already exist).
- Data quality checks.

## 3. Naming Standard

| Part    | Pattern                                                | Example                                                                 |
| ------- | ------------------------------------------------------ | ----------------------------------------------------------------------- |
| Catalog | `uc_{region}_{country}_{environment}`                  | `uc_sa_br_dev`                                                          |
| Schema (bronze/silver) | `{layer}_{domain}_{subdomain}`          | `bronze_binance_ohlcv` / `silver_market_ohlcv`                          |
| Schema (gold)          | `{layer}_{domain}_{subdomain}_{data_product}` | `gold_finance_investments_market_analysis`                      |
| Table   | `{table_name}`                                         | `daily`                                                               |
| FQN     | `{catalog}.{schema}.{table_name}`                      | `uc_sa_br_dev.bronze_binance_ohlcv.daily`                            |

Each medallion layer is organised by a different principle, so the `domain`/`subdomain` controlled vocabulary is **layer-dependent**:

- **bronze** — by **source**: `domain` is the exchange/provider, `subdomain` the context landed from it (e.g. `binance` / `ohlcv`).
- **silver** — by **context**: the same data from all exchanges is merged, so the source drops out of the name. `domain` is the conformed area, `subdomain` the entity (e.g. `market` / `ohlcv`, `market` / `tickers`). The originating exchange is kept as a column in the data, not in the schema name.
- **gold** — by **business / data product**: `domain` and `subdomain` describe the analytical product (not the source), and a free-form `data_product` completes the name (e.g. `finance` / `investments` / `market_analysis`).

Reference example values:

| Param          | Value (bronze)     | Validated by                  |
| -------------- | ------------------ | ----------------------------- |
| `country`      | `br`               | controlled vocabulary         |
| `region`       | `sa`               | format (free-form)            |
| `environment`  | `dev`              | controlled vocabulary         |
| `layer`        | `bronze`           | controlled vocabulary         |
| `domain`       | `binance`          | controlled vocabulary (per layer)  |
| `subdomain`    | `ohlcv`            | controlled vocabulary (per layer + domain) |
| `data_product` | `market_analysis` (gold only) | format (free-form)    |
| `table_name`   | `daily`            | format (free-form)            |

## 4. Validation Model

Each name part is validated in one of two ways.

### 4.1 Controlled vocabulary (allow-list)

Fields: `layer`, `country`, `domain`, `subdomain`, `environment`.

The value must be a **key** present in the corresponding dictionary; otherwise `GovernanceError` is raised. This enforcement keeps every developer using the same agreed terms.

`subdomain` is validated **per domain**: the value must be a key under the chosen domain. So `domain` must be valid first, then `subdomain` is checked against that domain's set.

The `domain`/`subdomain` vocabulary depends on the `layer`:

- **bronze** — validated against `BRONZE_DOMAINS` / `BRONZE_SUBDOMAINS`, where `domain` is the data **source** (the exchange / provider we ingest from) and `subdomain` is the **context** landed from it (e.g. `binance` / `ohlcv`).
- **silver** — validated against `SILVER_DOMAINS` / `SILVER_SUBDOMAINS`. The same data from all exchanges is merged by context, so the source drops out of the name: `domain` is the conformed area, `subdomain` the entity (e.g. `market` / `ohlcv`). The originating exchange is kept as a column, not in the name.
- **gold** — validated against `GOLD_DOMAINS` / `GOLD_SUBDOMAINS`, where `domain` and `subdomain` describe the **business / data product** rather than the source (e.g. `finance` / `investments`), completed by the free-form `data_product` (e.g. `market_analysis`).

`layer` is validated first, so the correct vocabulary is selected before `domain`/`subdomain` are checked (via the `DOMAIN_VOCAB_BY_LAYER` map).

The dictionaries are module-level constants in `src/zordon/vocabularies.py` (a single shared source of truth). The project owner edits them once; because everyone imports the same package, everyone gets the same allowed values. Flat dictionaries map `allowed_value -> short description`; the `*_SUBDOMAINS` dictionaries are nested by domain:

```python
LAYERS = {
    "bronze": "raw / landing layer",
    "silver": "cleaned, conformed layer",
    "gold":   "business-ready layer",
}

COUNTRIES = {
    "br": "Brazil",
    "fr": "France",
    "us": "United States",
}

ENVIRONMENTS = {
    "dev": "development",
    "prd": "production",
}

# Contexts (entities) shared by bronze (per source) and silver (conformed),
# so the two layers stay in sync:
_MARKET_CONTEXTS = {
    "ohlcv":   "OHLCV candles (open/high/low/close/volume)",
    "symbols": "trading pairs / instrument reference",
    "tickers": "24h ticker statistics",
    "orders":  "order / trade data",
}

# --- Bronze: by SOURCE ------------------------------------------------------
# domain = source (exchange/provider), subdomain = context landed from it:
#   binance         -> ohlcv, symbols, tickers, orders
#   poloniex        -> ohlcv, symbols, tickers, orders
#   alternative_me  -> fear_greed

BRONZE_DOMAINS = {
    "binance":        "Binance Spot API (price & volume / OHLCV)",
    "poloniex":       "Poloniex Spot API (price & volume / OHLCV)",
    "alternative_me": "Alternative.me (Fear & Greed Index / sentiment)",
}

# nested: domain -> {subdomain: description}
BRONZE_SUBDOMAINS = {
    "binance":        dict(_MARKET_CONTEXTS),
    "poloniex":       dict(_MARKET_CONTEXTS),
    "alternative_me": {"fear_greed": "Fear & Greed Index sentiment readings"},
}

# --- Silver: by CONTEXT (conformed across sources) --------------------------
# Sources merged; domain = conformed area, subdomain = entity:
#   market     -> ohlcv, symbols, tickers, orders
#   sentiment  -> fear_greed

SILVER_DOMAINS = {
    "market":    "market data conformed/merged across all exchanges",
    "sentiment": "market sentiment conformed across sources",
}

# nested: domain -> {subdomain: description}
SILVER_SUBDOMAINS = {
    "market":    dict(_MARKET_CONTEXTS),
    "sentiment": {"fear_greed": "Fear & Greed Index sentiment readings"},
}

# --- Gold: by BUSINESS / DATA PRODUCT ---------------------------------------
# Domain/subdomain describe the analytical product, not the source. Completed
# by the free-form data_product. Example:
#   domain="finance", subdomain="investments", data_product="market_analysis"

GOLD_DOMAINS = {
    "finance": "finance / market analytics domain",
}

# nested: gold_domain -> {gold_subdomain: description}
GOLD_SUBDOMAINS = {
    "finance": {
        "investments": "asset performance, risk & correlation analytics",
        "sentiment":   "market sentiment analytics (Fear & Greed integration)",
    },
}
```

Notes:
- The dictionary keys must themselves be lowercase snake_case, otherwise the generated catalog/schema names would be invalid.
- Each `*_SUBDOMAINS` dict's keys must stay in sync with the matching `*_DOMAINS` keys. A domain present in the domain dict but missing from the subdomain dict will reject every subdomain.
- `DOMAIN_VOCAB_BY_LAYER` maps each layer to its `(domains, subdomains)` pair; it is what `Governance` uses to pick the allow-list.
- Crypto-market (CryptoLake) interpretation: bronze domains are the sources (Binance/Poloniex exchanges and the Alternative.me sentiment provider); silver domains are the conformed areas (`market`, `sentiment`) merged across sources; gold domains/subdomains are the analytical products built on top.

### 4.2 Free-form format check

Fields: `region`, `data_product` (gold layer only), `table_name`.

These have no fixed list, so they are only checked for format. The value must:

- be a non-empty string,
- match the regex `^[a-z][a-z0-9]*(_[a-z0-9]+)*$` (lowercase, starts with a letter, single underscores only, characters `[a-z0-9_]`),
- not be in the reserved-word exclusion list.

Reserved-word list (kept intentionally small): `select, from, where, table, catalog, schema, database, create, drop, insert, update, delete, grant, user, order, group, by, join, on, as`.

Any violation raises `GovernanceError`.

## 5. Classes and Methods

### 5.1 `GovernanceError(Exception)`

Raised whenever a name part fails either validation tier. No custom attributes.

### 5.2 `Governance`

Validates the naming inputs and builds catalog / schema / FQN names. All parts are validated on construction, so an invalid `Governance` object can never be created.

| Method               | Description                                                                                            | Parameters                                                                                                                              | Returns                              |
| -------------------- | ------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------ |
| `__init__`           | Stores all name parts and validates each one (vocabulary or format as appropriate). Raises if invalid.  | `country: str`, `region: str`, `environment: str`, `layer: str`, `domain: str`, `subdomain: str`, `data_product: str = None` (required for gold, forbidden otherwise) | `None`                               |
| `validate_name`      | Format check for a free-form name part.                                                                 | `name: str`, `label: str = "name"`                                                                                                      | `bool` (or raises `GovernanceError`) |
| `validate_vocabulary`| Membership check of a value against an allow-list dictionary (flat).                                    | `value: str`, `allowed: dict`, `label: str = "name"`                                                                                    | `bool` (or raises `GovernanceError`) |
| `catalog_name`       | Builds the Unity Catalog catalog name.                                                                  | none                                                                                                                                    | `str`                                |
| `schema_name`        | Builds the Unity Catalog schema name.                                                                   | none                                                                                                                                    | `str`                                |
| `fqn`                | Validates `table_name` (format), then builds the 3-part fully qualified name.                           | `table_name: str`                                                                                                                       | `str` (or raises `GovernanceError`)  |

Behaviour details:
- `__init__` validation order:
  1. `layer` against `LAYERS`,
  2. `country` against `COUNTRIES`,
  3. `environment` against `ENVIRONMENTS`,
  4. `domain` against the layer's domain dict (`DOMAIN_VOCAB_BY_LAYER[layer][0]`),
  5. `subdomain` against the layer's subdomain dict for that domain (domain must already be valid),
  6. free-form `region` via `validate_name`.
  7. `data_product`: required and format-validated when `layer == "gold"`; must be omitted (`None`) for `bronze`/`silver`, otherwise raises.
  - The first invalid part raises and stops construction.
  - Because `layer` is validated first, the right domain/subdomain vocabulary is always selected before `domain`/`subdomain` are checked.
- `validate_vocabulary` raises listing the allowed keys, e.g. `"'layer'='raw' is not allowed. Allowed: ['bronze', 'silver', 'gold']"`. For the subdomain it is called with `subdomains.get(domain, {})` for the layer's subdomain dict.
- `catalog_name` returns `f"uc_{region}_{country}_{environment}"`.
- `schema_name` is layer-dependent:
  - gold: `f"{layer}_{domain}_{subdomain}_{data_product}"`,
  - bronze/silver: `f"{layer}_{domain}_{subdomain}"`.
- `fqn` returns `f"{catalog_name()}.{schema_name()}.{table_name}"`; `table_name` is free-form and validated with `validate_name`.

### 5.3 `DataClient`

Reads and writes managed Delta tables using names from a `Governance` instance.

| Method        | Description                                                                                                                              | Parameters                                                                                          | Returns      |
| ------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- | ------------ |
| `__init__`     | Stores the Spark session and a `Governance` instance.                                                                                    | `spark: SparkSession`, `governance: Governance`                                                     | `None`       |
| `write_table`  | Validates the table name, runs `CREATE SCHEMA IF NOT EXISTS`, then writes a managed Delta table with `saveAsTable`. Returns the FQN used. | `df: DataFrame`, `table_name: str`, `mode: str = "overwrite"`, `partition_cols: list[str] = None`, `dynamic_partition_overwrite: bool = False` | `str` (FQN)  |
| `upsert_table` | Validates the name, ensures the schema, then upserts via Delta `MERGE` on `merge_keys` (creating the table on first use). Returns the FQN. | `df: DataFrame`, `table_name: str`, `merge_keys: str \| list[str]`, `partition_cols: list[str] = None` | `str` (FQN)  |
| `read_table`   | Reads a table by its short name, resolved to the project's FQN, optionally applying filters (partition pruning / incremental reads).      | `table_name: str`, `filters: str \| dict \| list \| Column = None`                                   | `DataFrame`  |

Behaviour details:
- `write_table`:
  - `mode` must be `"append"` or `"overwrite"`; anything else raises `ValueError`.
  - Resolves the FQN via `governance.fqn(table_name)` (which re-validates the name).
  - Executes ``CREATE SCHEMA IF NOT EXISTS `{catalog}`.`{schema}` `` (via the internal `_ensure_schema` helper, shared with `upsert_table`).
  - Writes via `df.write.format("delta").mode(mode)`, applying `.partitionBy(*partition_cols)` only when `partition_cols` is provided, then `.saveAsTable(fqn)`.
  - `dynamic_partition_overwrite=True` adds the `partitionOverwriteMode=dynamic` writer option, so an `"overwrite"` only replaces the partitions present in `df` (not the whole table). It is only valid with `mode="overwrite"`; combined with `"append"` it raises `ValueError`.
  - Returns the FQN string.
  - Assumes the catalog already exists; if it does not, the `CREATE SCHEMA` statement fails with a Spark error.
- `upsert_table`:
  - `merge_keys` may be a single column name or a list; empty or non-identifier keys raise `ValueError`.
  - Ensures the schema, then resolves the FQN.
  - If the table does not exist yet (`spark.catalog.tableExists`), it is created with a plain overwrite write (honouring `partition_cols`), so the first call behaves like `write_table`.
  - If the table exists, runs a Delta `MERGE` matching on ``t.<key> = s.<key>`` for every key (AND-combined), `whenMatchedUpdateAll().whenNotMatchedInsertAll()`.
  - `partition_cols` is only used on the create path; it is ignored once the table exists.
  - Imports `delta.tables.DeltaTable` lazily, so importing `zordon` off Databricks does not require the `delta` package.
- `read_table`:
  - Resolves the table via `spark.read.table(governance.fqn(table_name))`.
  - When `filters is None`, returns the full DataFrame.
  - `filters` may be a SQL string expression (`"rate_date >= '2026-06-01'"`), a dict of `column -> value` applied as equalities and AND-combined (`{"rate_date": "2026-06-17"}`), a list/tuple of conditions (strings or Columns) applied in sequence, or a Spark Column.
  - Each condition is applied with `DataFrame.filter`. When it targets a partition column, Spark/Delta prunes partitions at the file level, so an incremental read scans only the partitions it needs.

### 5.4 `Project`

A factory that holds the constant catalog parts (`country` / `region` / `environment`) and builds per-schema `Governance` / `DataClient` objects. A `Governance`/`DataClient` is bound to one schema, so a notebook that reads several silver schemas and writes several gold schemas would otherwise repeat the catalog parts for each; `Project` states them once.

| Method        | Description                                                                                  | Parameters                                                                                  | Returns                  |
| ------------- | -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- | ------------------------ |
| `__init__`    | Stores the Spark session and the catalog parts.                                              | `spark: SparkSession`, `country: str`, `region: str`, `environment: str`                     | `None`                   |
| `governance`  | Builds a validated `Governance` for one schema, reusing the catalog parts.                   | `layer: str`, `domain: str`, `subdomain: str`, `data_product: str = None`                    | `Governance`             |
| `client`      | Builds a `DataClient` bound to one schema (validates the parts up front).                     | `layer: str`, `domain: str`, `subdomain: str`, `data_product: str = None`                    | `DataClient`             |

Behaviour details:
- `governance` / `client` delegate validation to `Governance.__init__`, so the same per-layer vocabulary rules and the gold-only `data_product` rule apply, and invalid parts raise `GovernanceError`.
- You need a new `client` only when the **schema** changes; multiple tables in the same schema (e.g. several gold fact/dimension tables) reuse one client.

## 6. Usage Example

```python
import zordon

# Bronze: by source (domain) + context (subdomain), no data_product.
gov = zordon.Governance(
    country="br", region="sa", environment="dev",
    layer="bronze", domain="binance", subdomain="ohlcv",
)
# layer "raw" would raise (only bronze/silver/gold allowed);
# subdomain "fear_greed" under domain "binance" would raise (wrong domain);
# domain "market" would raise in bronze (that is a silver domain);
# passing data_product on a bronze layer would raise.

client = zordon.DataClient(spark, gov)

# write -> uc_sa_br_dev.bronze_binance_ohlcv.daily
client.write_table(df, "daily", mode="overwrite", partition_cols=["rate_date"])

# reprocess only the partitions present in df (dynamic partition overwrite)
client.write_table(df, "daily", mode="overwrite", partition_cols=["rate_date"],
                   dynamic_partition_overwrite=True)

# upsert: update matched rows / insert new ones, keyed on (symbol, rate_date)
client.upsert_table(df, "daily", merge_keys=["symbol", "rate_date"],
                    partition_cols=["rate_date"])

# full read
df2 = client.read_table("daily")

# incremental read — partition pruning on the partition column
df3 = client.read_table("daily", filters="rate_date >= '2026-06-01'")
df4 = client.read_table("daily", filters={"rate_date": "2026-06-17"})

# Silver: exchanges merged, organised by context.
silver = zordon.Governance(
    country="br", region="sa", environment="dev",
    layer="silver", domain="market", subdomain="ohlcv",
)
# schema -> silver_market_ohlcv

# Gold: adds the data_product as a fourth schema part (by business product).
gold = zordon.Governance(
    country="br", region="sa", environment="dev",
    layer="gold", domain="finance", subdomain="investments",
    data_product="market_analysis",
)
# schema -> gold_finance_investments_market_analysis

# A notebook that spans layers (read silver, write gold) is terser with a
# Project: catalog parts stated once, one client per schema.
proj = zordon.Project(spark, country="br", region="sa", environment="dev")

silver = proj.client(layer="silver", domain="market", subdomain="ohlcv")
gold   = proj.client(layer="gold", domain="finance",
                     subdomain="investments", data_product="market_analysis")

fact = silver.read_table("daily")            # ... joins / transforms ...
gold.write_table(fact, "fact_ohlcv", partition_cols=["rate_date"])
gold.write_table(dim_symbol, "dim_symbol")   # same schema -> reuse the client
```

## 7. Distribution

`zordon` is a `src`-layout Python package:

```
src/zordon/
    __init__.py     # public API re-exports + __version__
    project.py      # Project (factory for per-schema clients)
    governance.py   # Governance
    client.py       # DataClient
    vocabularies.py # controlled vocabularies (allowed values)
    errors.py       # GovernanceError
pyproject.toml      # build/install configuration
tests/              # unit tests (no Spark required)
```

The public API is re-exported from `zordon/__init__.py`, so consumers always write `import zordon` / `from zordon import Project, Governance, DataClient` regardless of the module split.

Three supported deployment paths (details in the README):

1. **Source on `sys.path`** — add the `src` folder to `sys.path` and import directly. Best for active development.

   ```python
   import sys; sys.path.append("/Workspace/Repos/<you>/zordon-data-utils/src")
   import zordon
   ```

2. **Editable install** — `pip install -e <repo>` on the cluster/notebook so plain `import zordon` works without `sys.path`.

3. **Wheel** — build with `python -m build` (or `pip wheel . --no-deps`) and install the resulting `dist/zordon-<version>-py3-none-any.whl` as a cluster library. Recommended once the vocabularies are stable.

PySpark is the only runtime dependency and is already present on Databricks, so it is declared as an optional `[spark]`/`[dev]` extra (for local testing) rather than a hard dependency in `pyproject.toml`.

## 8. Design Notes

- Layers: `bronze`, `silver`, `gold`.
- Environments: `dev`, `prd`.
- `data_product` is part of the schema name on the **gold** layer only. Bronze and silver schemas are named `{layer}_{domain}_{subdomain}`; passing `data_product` to a non-gold layer raises, and omitting it on gold raises.
- The `domain`/`subdomain` vocabulary is **layer-dependent**, because each layer is organised differently. Subdomains are nested per domain (a subdomain is only valid under its own domain).
- Domain/subdomain hierarchy:
  - bronze (by source):
    - `binance` -> `ohlcv`, `symbols`, `tickers`, `orders`
    - `poloniex` -> `ohlcv`, `symbols`, `tickers`, `orders`
    - `alternative_me` -> `fear_greed`
  - silver (conformed by context, sources merged):
    - `market` -> `ohlcv`, `symbols`, `tickers`, `orders`
    - `sentiment` -> `fear_greed`
  - gold (by business product):
    - `finance` -> `investments`, `sentiment` (+ free-form `data_product`)
- Allowed values are dictionary **keys**; values are descriptions only.
- Controlled fields: `layer, country, domain, subdomain, environment`. Free-form fields: `region, data_product (gold only), table_name`.
- `read_table` supports optional `filters` for partition pruning / incremental reads.
- `write_table` supports `dynamic_partition_overwrite` to replace only the partitions present in the DataFrame (`partitionOverwriteMode=dynamic`).
- `upsert_table` performs a Delta `MERGE` on a set of key columns, creating the table on first use. `delta.tables.DeltaTable` is imported lazily so importing `zordon` off Databricks does not require the `delta` package.
- A `Governance`/`DataClient` is bound to one schema. `Project` is the factory for multi-schema notebooks: it holds the catalog parts and builds one client per schema, delegating validation to `Governance`.
- The vocabularies are module-level constants in `src/zordon/vocabularies.py`, one shared source of truth edited by the project owner (not passed per developer). The bronze and silver context lists share the `_MARKET_CONTEXTS` dict, so editing it updates both layers together.
- The Unity Catalog catalog is created once by the project owner and shared; the library never creates it.
- `country` and `region` are both part of the catalog name, matching the documented naming standard.
