# zordon — Library Specification

Version: 1.2
Status: reference / validation document

## 1. Purpose

`zordon` is a small helper library for a student data-engineering project on
Databricks (PySpark). Its single objective is to make every developer working
on the project in parallel follow the **same naming rules** for Unity Catalog
(catalog / schema / table), and to write managed Delta tables to those names.

It is **not** installed on the cluster. It is a single `.py` file imported into
notebooks.

## 2. Scope

In scope (v1.2):
- Two-tier validation of naming inputs:
  - controlled vocabulary (value must exist in a fixed dictionary), and
  - free-form format (lowercase snake_case).
- Construction of catalog, schema and fully qualified names (FQN).
- Writing **managed** Delta tables to Unity Catalog.
- Reading tables back by short name.

Out of scope:
- External tables / ADLS Gen2 URIs (managed tables only).
- Permissions / `GRANT`.
- `CREATE CATALOG` (catalog is assumed to already exist).
- Data quality checks.
- `MERGE` / upsert operations.

## 3. Naming Standard

| Part    | Pattern                                                | Example                                                                 |
| ------- | ------------------------------------------------------ | ----------------------------------------------------------------------- |
| Catalog | `{prefix}_uc_{country}_{region}_{environment}`         | `proj_uc_br_sa_dev`                                                     |
| Schema  | `{layer}_{domain}_{subdomain}_{data_product}`          | `bronze_sales_crm_events_user_interaction`                             |
| Table   | `{table_name}`                                         | `log`                                                                  |
| FQN     | `{catalog}.{schema}.{table_name}`                      | `proj_uc_br_sa_dev.bronze_sales_crm_events_user_interaction.log`       |

Reference example values:

| Param          | Value              | Validated by                  |
| -------------- | ------------------ | ----------------------------- |
| `prefix`       | `proj`             | format (free-form)            |
| `country`      | `br`               | controlled vocabulary         |
| `region`       | `sa`               | format (free-form)            |
| `environment`  | `dev`              | controlled vocabulary         |
| `layer`        | `bronze`           | controlled vocabulary         |
| `domain`       | `sales`            | controlled vocabulary         |
| `subdomain`    | `crm_events`       | controlled vocabulary (per domain) |
| `data_product` | `user_interaction` | format (free-form)            |
| `table_name`   | `log`              | format (free-form)            |

## 4. Validation Model

Each name part is validated in one of two ways.

### 4.1 Controlled vocabulary (allow-list)

Fields: `layer`, `country`, `domain`, `subdomain`, `environment`.

The value must be a **key** present in the corresponding dictionary; otherwise
`GovernanceError` is raised. This enforcement keeps every developer using the
same agreed terms.

`subdomain` is validated **per domain**: the value must be a key under the
chosen domain. So `domain` must be valid first, then `subdomain` is checked
against that domain's set.

The dictionaries are module-level constants in `zordon.py` (a single shared
source of truth). The project owner edits them once; because everyone imports
the same file, everyone gets the same allowed values. Flat dictionaries map
`allowed_value -> short description`; `SUBDOMAINS` is nested by domain:

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

# Domain / subdomain hierarchy (keys of SUBDOMAINS must match keys of DOMAINS):
#
#   sales      -> crm_events, orders
#   marketing  -> campaigns, web_analytics
#   finance    -> exchanges (confirmed), invoices (proposed)

DOMAINS = {
    "sales":     "sales domain",
    "marketing": "marketing domain",
    "finance":   "finance domain",
}

# nested: domain -> {subdomain: description}
SUBDOMAINS = {
    "sales":     {"crm_events": "CRM event data", "orders": "order data"},
    "marketing": {"campaigns": "campaign data", "web_analytics": "web analytics data"},
    "finance":   {"exchanges": "exchange / FX data", "invoices": "invoice data"},
}
```

Notes:
- The dictionary keys must themselves be lowercase snake_case, otherwise the
  generated catalog/schema names would be invalid.
- `SUBDOMAINS` keys must stay in sync with `DOMAINS` keys. A domain valid in
  `DOMAINS` but missing from `SUBDOMAINS` will reject every subdomain.
- All values shown are placeholders except the confirmed ones (bronze/silver/gold
  layers, dev/prd environments, `exchanges` under finance).

### 4.2 Free-form format check

Fields: `prefix`, `region`, `data_product`, `table_name`.

These have no fixed list, so they are only checked for format. The value must:

- be a non-empty string,
- match the regex `^[a-z][a-z0-9]*(_[a-z0-9]+)*$` (lowercase, starts with a
  letter, single underscores only, characters `[a-z0-9_]`),
- not be in the reserved-word exclusion list.

Reserved-word list (kept intentionally small):
`select, from, where, table, catalog, schema, database, create, drop, insert,
update, delete, grant, user, order, group, by, join, on, as`.

Any violation raises `GovernanceError`.

## 5. Classes and Methods

### 5.1 `GovernanceError(Exception)`

Raised whenever a name part fails either validation tier. No custom attributes.

### 5.2 `Governance`

Validates the naming inputs and builds catalog / schema / FQN names. All parts
are validated on construction, so an invalid `Governance` object can never be
created.

| Method               | Description                                                                                            | Parameters                                                                                                                              | Returns                              |
| -------------------- | ------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------ |
| `__init__`           | Stores all name parts and validates each one (vocabulary or format as appropriate). Raises if invalid.  | `prefix: str`, `country: str`, `region: str`, `environment: str`, `layer: str`, `domain: str`, `subdomain: str`, `data_product: str`     | `None`                               |
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
  4. `domain` against `DOMAINS`,
  5. `subdomain` against `SUBDOMAINS[domain]` (domain must already be valid),
  6. free-form `prefix`, `region`, `data_product` via `validate_name`.
  - The first invalid part raises and stops construction.
- `validate_vocabulary` raises listing the allowed keys, e.g.
  `"'layer'='raw' is not allowed. Allowed: ['bronze', 'silver', 'gold']"`.
  For the subdomain it is called with `SUBDOMAINS.get(domain, {})`.
- `catalog_name` returns `f"{prefix}_uc_{country}_{region}_{environment}"`.
- `schema_name` returns `f"{layer}_{domain}_{subdomain}_{data_product}"`.
- `fqn` returns `f"{catalog_name()}.{schema_name()}.{table_name}"`; `table_name`
  is free-form and validated with `validate_name`.

### 5.3 `DataClient`

Reads and writes managed Delta tables using names from a `Governance` instance.

| Method        | Description                                                                                                                              | Parameters                                                                                          | Returns      |
| ------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- | ------------ |
| `__init__`    | Stores the Spark session and a `Governance` instance.                                                                                    | `spark: SparkSession`, `governance: Governance`                                                     | `None`       |
| `write_table` | Validates the table name, runs `CREATE SCHEMA IF NOT EXISTS`, then writes a managed Delta table with `saveAsTable`. Returns the FQN used. | `df: DataFrame`, `table_name: str`, `mode: str = "overwrite"`, `partition_cols: list[str] = None`   | `str` (FQN)  |
| `read_table`  | Reads a table by its short name, resolved to the project's FQN.                                                                          | `table_name: str`                                                                                   | `DataFrame`  |

Behaviour details:
- `write_table`:
  - `mode` must be `"append"` or `"overwrite"`; anything else raises `ValueError`.
  - Resolves the FQN via `governance.fqn(table_name)` (which re-validates the name).
  - Executes ``CREATE SCHEMA IF NOT EXISTS `{catalog}`.`{schema}` ``.
  - Writes via `df.write.format("delta").mode(mode)`, applying
    `.partitionBy(*partition_cols)` only when `partition_cols` is provided, then
    `.saveAsTable(fqn)`.
  - Returns the FQN string.
  - Assumes the catalog already exists; if it does not, the `CREATE SCHEMA`
    statement fails with a Spark error.
- `read_table` returns `spark.read.table(governance.fqn(table_name))`.

## 6. Usage Example

```python
import zordon

gov = zordon.Governance(
    prefix="proj", country="br", region="sa", environment="dev",
    layer="bronze", domain="finance", subdomain="exchanges",
    data_product="fx_rates",
)
# layer "raw" would raise (only bronze/silver/gold allowed);
# subdomain "crm_events" under domain "finance" would raise (wrong domain).

client = zordon.DataClient(spark, gov)

# write -> proj_uc_br_sa_dev.bronze_finance_exchanges_fx_rates.daily
client.write_table(df, "daily", mode="overwrite", partition_cols=["rate_date"])

df2 = client.read_table("daily")
```

## 7. Distribution

Single file `zordon.py` placed in the project's Workspace folder or Repo.
Import from a notebook with either:

```python
%run ./zordon
```

or:

```python
import sys
sys.path.append("/Workspace/path/to/folder")
import zordon
```

Only dependency is PySpark, already present on Databricks.

## 8. Confirmed Decisions and Remaining Notes

Confirmed:
- Layers: `bronze`, `silver`, `gold`.
- Environments: `dev`, `prd` (staging removed).
- Subdomains are nested per domain (a subdomain is only valid under its own domain).
- Defined domain/subdomain hierarchy:
  - `sales` -> `crm_events`, `orders`
  - `marketing` -> `campaigns`, `web_analytics`
  - `finance` -> `exchanges` (confirmed), `invoices` (proposed)
- Allowed values are dictionary **keys**; values are descriptions only.
- Controlled fields: `layer, country, domain, subdomain, environment`.
  Free-form fields: `prefix, region, data_product, table_name`.
- Dictionaries are fixed module-level constants edited once by the project owner
  (one shared vocabulary, not passed per developer).
- The Unity Catalog catalog is created once by the project owner and shared; the
  library never creates it.

Still to confirm / placeholder (edit to your real project):
- `COUNTRIES` values.
- The subdomain names other than `exchanges` (proposed; replace with real ones).
- The reserved-word list (minimal; tune if needed).
- `country` + `region` redundancy is accepted to match the documented standard.
