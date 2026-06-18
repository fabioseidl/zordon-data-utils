# zordon — User Guide

`zordon` is a small helper for our Databricks project. It exists so that every
developer working on the project in parallel writes tables to Unity Catalog
using the **same naming rules**. You give it the parts of a name, it validates
them against the project's agreed vocabulary, and it writes a managed Delta
table to the correct location.

You do not need to learn Unity Catalog naming by hand — if a value is wrong,
`zordon` tells you, with the list of allowed values.

## 1. Setup

`zordon` is a single file (`zordon.py`) kept in the project's Workspace folder
or Repo. It is **not** installed on the cluster. Import it in a notebook with
either:

```python
%run ./zordon
```

or, if the file is elsewhere in the Workspace:

```python
import sys
sys.path.append("/Workspace/path/to/folder")
import zordon
```

The only dependency is PySpark, which Databricks already provides. The `spark`
session is also already available in any Databricks notebook.

## 2. Quick start

```python
import zordon

gov = zordon.Governance(
    prefix="proj",
    country="br",
    region="sa",
    environment="dev",
    layer="bronze",
    domain="finance",
    subdomain="exchanges",
    data_product="fx_rates",
)

client = zordon.DataClient(spark, gov)

# writes to: proj_uc_br_sa_dev.bronze_finance_exchanges_fx_rates.daily
client.write_table(df, "daily", mode="overwrite", partition_cols=["rate_date"])

# read it back
df2 = client.read_table("daily")
```

If any value is not allowed, `Governance(...)` raises immediately with a clear
message, so you fix it before anything is written.

## 3. How names are built

`zordon` builds three names from the parts you pass:

| Name    | Built as                                            | Example                                                            |
| ------- | --------------------------------------------------- | ------------------------------------------------------------------ |
| Catalog | `{prefix}_uc_{country}_{region}_{environment}`      | `proj_uc_br_sa_dev`                                                |
| Schema  | `{layer}_{domain}_{subdomain}_{data_product}`       | `bronze_finance_exchanges_fx_rates`                               |
| Table   | `{table_name}` (you pass this to `write_table`)     | `daily`                                                           |
| FQN     | `{catalog}.{schema}.{table_name}`                   | `proj_uc_br_sa_dev.bronze_finance_exchanges_fx_rates.daily`       |

## 4. Allowed values

Five fields must use a value from the project's agreed list. If you use anything
else, you get a `GovernanceError`.

Layer:

| Value    | Meaning                  |
| -------- | ------------------------ |
| `bronze` | raw / landing layer      |
| `silver` | cleaned, conformed layer |
| `gold`   | business-ready layer     |

Country:

| Value | Meaning       |
| ----- | ------------- |
| `br`  | Brazil        |
| `fr`  | France        |
| `us`  | United States |

Environment:

| Value | Meaning     |
| ----- | ----------- |
| `dev` | development |
| `prd` | production  |

Domain and subdomain (a subdomain is only valid under its own domain):

| Domain      | Allowed subdomains            |
| ----------- | ----------------------------- |
| `sales`     | `crm_events`, `orders`        |
| `marketing` | `campaigns`, `web_analytics`  |
| `finance`   | `exchanges`, `invoices`       |

So `subdomain="exchanges"` works with `domain="finance"`, but the same subdomain
with `domain="sales"` is rejected.

The remaining fields are free-form and only need to be lowercase snake_case:
`prefix`, `region`, `data_product`, and the `table_name` you pass to
`write_table`. "snake_case" here means: starts with a letter, only lowercase
letters, digits and single underscores, no leading/trailing/double underscore
(for example `fx_rates`, `daily`, `user_interaction`). Reserved SQL words such
as `select` or `table` are also rejected.

## 5. API

### `Governance(...)`

Validates all naming parts and builds names. Constructing it with an invalid
value raises `GovernanceError`.

Parameters: `prefix`, `country`, `region`, `environment`, `layer`, `domain`,
`subdomain`, `data_product` (all strings).

Useful methods:
- `catalog_name()` returns the catalog string.
- `schema_name()` returns the schema string.
- `fqn(table_name)` returns the full three-part name for a given table.

### `DataClient(spark, governance)`

Writes and reads managed Delta tables using the names from a `Governance`
object.

- `write_table(df, table_name, mode="overwrite", partition_cols=None)`
  Validates the table name, creates the schema if it does not exist, writes the
  DataFrame as a managed Delta table, and returns the full name it wrote to.
  `mode` is `"overwrite"` or `"append"`. `partition_cols` is an optional list of
  column names to partition by.
- `read_table(table_name)`
  Returns the table as a DataFrame, resolved to the project's full name.

## 6. Common errors

| Message you see                                          | Cause                                                              | Fix                                                        |
| -------------------------------------------------------- | ------------------------------------------------------------------ | ---------------------------------------------------------- |
| `'layer'='raw' is not allowed. Allowed: [...]`           | A controlled field uses a value outside the agreed list.           | Use one of the listed values.                              |
| `'subdomain (domain='finance')'='crm_events' is not allowed` | The subdomain is valid, but not under that domain.             | Use a subdomain that belongs to the domain you chose.      |
| `'prefix'='Proj' is not valid lowercase snake_case`      | A free-form field has uppercase, spaces, or bad underscores.       | Use lowercase snake_case.                                  |
| `'data_product'='select' is a reserved word`             | A free-form field uses a reserved SQL word.                        | Pick a different name.                                     |
| `mode must be one of ('append', 'overwrite')`            | `write_table` got an unsupported mode.                             | Use `"overwrite"` or `"append"`.                           |
| A Spark error on `CREATE SCHEMA`                          | The catalog does not exist yet.                                    | Ask the project owner to create the shared catalog first.  |

## 7. Good to know

- The catalog is created once by the project owner and shared. `zordon` creates
  the schema automatically but never the catalog.
- The allowed values live in `zordon.py` as `LAYERS`, `COUNTRIES`,
  `ENVIRONMENTS`, `DOMAINS` and `SUBDOMAINS`. To add or change an allowed value,
  the project owner edits that one file; because everyone imports the same file,
  the change reaches everyone.
- `zordon` only writes managed Delta tables. It does not handle external tables,
  permissions, merges, or data-quality checks.
