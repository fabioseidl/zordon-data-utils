# zordon — User Guide

`zordon` is a small helper for our mentory Databricks project. It exists so that every developer working on the project in parallel writes tables to Unity Catalog using the **same naming rules**. You give it the parts of a name, it validates them against the project's agreed vocabulary, and it writes a managed Delta table to the correct location.

You do not need to learn Unity Catalog naming by hand — if a value is wrong, `zordon` tells you, with the list of allowed values.

`zordon` is a Python package. Its only runtime dependency is PySpark, which the Databricks runtime already provides, so nothing else needs to be installed to use it.

## 1. Project structure

```
zordon-data-utils/
├── pyproject.toml          # build / install configuration (build a wheel from here)
├── README.md               # this guide
├── specs/zordon_spec.md    # detailed reference / validation spec
├── src/
│   └── zordon/             # the importable package
│       ├── __init__.py     # public API (Project, Governance, DataClient, ...)
│       ├── project.py      # Project: factory for per-schema clients
│       ├── governance.py   # Governance: validation + name building
│       ├── client.py       # DataClient: read/write managed Delta tables
│       ├── vocabularies.py # the controlled vocabularies (allowed values)
│       └── errors.py       # GovernanceError
└── tests/                  # unit tests (no Spark required)
```

You import it the same way regardless of how you set it up:

```python
import zordon
from zordon import Project, Governance, DataClient  # classes
from zordon import BRONZE_DOMAINS, GOLD_DOMAINS      # vocabularies, if you need them
```

## 2. Installing / making it importable

There are three ways to get `zordon` onto Databricks. Pick one.

### Option A — use the source directly in a notebook (quickest)

Put the `src/zordon/` folder in your Workspace/Repo, then point Python at the `src` folder before importing:

```python
import sys
sys.path.append("/Workspace/Repos/<you>/zordon-data-utils/src")
import zordon
```

Good for active development — edit the package, re-run, no rebuild needed (use `dbutils.library.restartPython()` or detach/reattach to pick up changes).

### Option B — editable/local install on the cluster

From the repo root (e.g. in a Repo or via a `%pip` cell that can see the path):

```python
%pip install -e /Workspace/Repos/<you>/zordon-data-utils
```

This installs `zordon` into the current notebook's Python so plain `import zordon` works without touching `sys.path`. `-e` keeps it editable.

### Option C — build a wheel and install it on the cluster (for sharing / prod)

Build a wheel once (locally or in CI):

```bash
python -m build            # produces dist/zordon-<version>-py3-none-any.whl
# or, without the `build` package:
python -m pip wheel . --no-deps -w dist
```

Then install the `.whl` on the cluster, either:

- **Cluster Libraries UI** → *Install new* → *Upload* (or DBFS/Volume path) → select the wheel, or
- in a notebook:

  ```python
  %pip install /Volumes/<catalog>/<schema>/<vol>/zordon-1.4.0-py3-none-any.whl
  ```

After install, `import zordon` works on every notebook attached to the cluster. This is the recommended path once the vocabularies are stable.

The `spark` session is already available in any Databricks notebook, so you do not create it yourself.

## 3. Quick start

```python
import zordon

gov = zordon.Governance(
    country="br",
    region="sa",
    environment="dev",
    layer="bronze",
    domain="binance",   # source (bronze is organised by exchange)
    subdomain="ohlcv",  # context landed from that source
    # data_product is only used on the gold layer
)

client = zordon.DataClient(spark, gov)

# writes to: uc_br_sa_dev.bronze_binance_ohlcv.daily
client.write_table(df, "daily", mode="overwrite", partition_cols=["rate_date"])

# overwrite only the partitions present in df (dynamic partition overwrite)
client.write_table(df, "daily", mode="overwrite", partition_cols=["rate_date"],
                   dynamic_partition_overwrite=True)

# upsert: update existing rows / insert new ones, matched on the key columns
client.upsert_table(df, "daily", merge_keys=["symbol", "rate_date"])

# read it back (full table)
df2 = client.read_table("daily")

# incremental read — only the partitions you need (partition pruning)
df3 = client.read_table("daily", filters="rate_date >= '2026-06-01'")
df4 = client.read_table("daily", filters={"rate_date": "2026-06-17"})
```

If any value is not allowed, `Governance(...)` raises immediately with a clear message, so you fix it before anything is written.

### Working across schemas (read silver → write gold)

A `Governance`/`DataClient` is bound to **one** schema (`layer` + `domain` + `subdomain` + optional `data_product`). A notebook that reads silver tables and writes gold fact/dimension tables therefore touches several schemas. Instead of building a `Governance` by hand for each one, use a `Project`: it holds the catalog parts (`country`/`region`/`environment`) once and hands you a client per schema.

```python
import zordon

proj = zordon.Project(spark, country="br", region="sa", environment="dev")

# one client per schema you read from / write to
silver_ohlcv   = proj.client(layer="silver", domain="market", subdomain="ohlcv")
silver_tickers = proj.client(layer="silver", domain="market", subdomain="tickers")
gold           = proj.client(layer="gold", domain="finance",
                             subdomain="investments", data_product="market_analysis")

ohlcv = silver_ohlcv.read_table("daily")
ticks = silver_tickers.read_table("daily")

fact = ohlcv.join(ticks, ["symbol", "rate_date"])   # your joins / transforms

# all gold tables in the same schema reuse the same client
gold.write_table(fact, "fact_ohlcv", partition_cols=["rate_date"])
gold.write_table(dim_symbol, "dim_symbol")
```

You only need a new client when the **schema** changes (a different `domain`/`subdomain`/`data_product`), not for every table — multiple fact/dim tables under the same gold schema share one client.

### Incremental upsert into a table

A common daily job: read **today's** partition from silver, transform it, and upsert the rows into a dimension keyed on its ID column — existing IDs are updated, new IDs inserted, and yesterday's rows are left untouched.

```python
import datetime
import zordon

proj = zordon.Project(spark, country="br", region="sa", environment="dev")

silver = proj.client(layer="silver", domain="market", subdomain="symbols")
gold   = proj.client(layer="gold", domain="finance",
                     subdomain="investments", data_product="market_analysis")

today = datetime.date.today().isoformat()   # e.g. "2026-06-18"

# read only today's partition (partition pruning on rate_date)
raw = silver.read_table("symbols", filters={"rate_date": today})

# transform into the dimension's shape; one row per business key
dim = (
    raw.select("symbol_id", "symbol", "base_asset", "quote_asset", "exchange")
       .dropDuplicates(["symbol_id"])
)

# upsert: match on the ID column -> update matched rows, insert new ones
gold.upsert_table(dim, "dim_symbol", merge_keys="symbol_id")
```

`merge_keys` is the ID to match on — a single column (`"symbol_id"`) or a list (`["symbol_id", "exchange"]`) for a composite key. On the very first run the `dim_symbol` table does not exist yet, so `upsert_table` creates it; every run after that performs the `MERGE`.

## 4. How names are built

`zordon` builds three names from the parts you pass:

| Name    | Built as                                            | Example                                                            |
| ------- | --------------------------------------------------- | ------------------------------------------------------------------ |
| Catalog | `uc_{country}_{region}_{environment}`               | `uc_br_sa_dev`                                                     |
| Schema (bronze/silver) | `{layer}_{domain}_{subdomain}`       | `bronze_binance_ohlcv` / `silver_market_ohlcv`                    |
| Schema (gold)          | `{layer}_{domain}_{subdomain}_{data_product}` | `gold_finance_investments_market_analysis`              |
| Table   | `{table_name}` (you pass this to `write_table`)     | `daily`                                                           |
| FQN     | `{catalog}.{schema}.{table_name}`                   | `uc_br_sa_dev.bronze_binance_ohlcv.daily`                       |

Each layer is organised by a different principle, so the `domain`/`subdomain` values you pass depend on the layer:

- **bronze** — by **source**: `domain` is the exchange (`binance`), `subdomain` the context landed from it (`ohlcv`).
- **silver** — by **context**: data from all exchanges is merged, so the source drops out. `domain` is the conformed area (`market`), `subdomain` the entity (`ohlcv`, `tickers`, ...). Which exchange a row came from is a column, not part of the name.
- **gold** — by **business product**: `domain`/`subdomain` describe the product (`finance` / `investments`) plus a `data_product` (`market_analysis`). `data_product` is **required for gold** and must be **omitted** for bronze/silver.

## 5. Allowed values

Five fields must use a value from the project's agreed list. If you use anything else, you get a `GovernanceError`.

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

Domain and subdomain — **the allowed values depend on the layer** (a subdomain is only valid under its own domain):

**bronze** (by source — the exchange/provider):

| Domain           | Allowed subdomains                    | Source                        |
| ---------------- | ------------------------------------- | ----------------------------- |
| `binance`        | `ohlcv`, `symbols`, `tickers`, `orders` | Binance Spot API            |
| `poloniex`       | `ohlcv`, `symbols`, `tickers`, `orders` | Poloniex Spot API           |
| `alternative_me` | `fear_greed`                          | Alternative.me Fear & Greed   |

**silver** (by context — exchanges merged, source kept as a column):

| Domain      | Allowed subdomains                      |
| ----------- | --------------------------------------- |
| `market`    | `ohlcv`, `symbols`, `tickers`, `orders` |
| `sentiment` | `fear_greed`                            |

**gold** (by business product — plus a free-form `data_product`):

| Domain    | Allowed subdomains          |
| --------- | --------------------------- |
| `finance` | `investments`, `sentiment`  |

So `domain="binance"` is valid in bronze but rejected in silver/gold; `fear_greed` is only valid under `alternative_me` (bronze) or `sentiment` (silver).

The remaining fields are free-form and only need to be lowercase snake_case: `region`, `data_product` (gold only), and the `table_name` you pass to `write_table`. "snake_case" here means: starts with a letter, only lowercase letters, digits and single underscores, no leading/trailing/double underscore (for example `market_analysis`, `daily`, `fear_greed`). Reserved SQL words such as `select` or `table` are also rejected.

## 6. API

### `Project(spark, country, region, environment)`

A factory that holds the constant catalog parts and builds per-schema objects, so a notebook touching several schemas states `country`/`region`/`environment` only once.

- `client(layer, domain, subdomain, data_product=None)` Returns a `DataClient` bound to that schema (validates the parts up front).
- `governance(layer, domain, subdomain, data_product=None)` Returns just the validated `Governance` for that schema, if you only need the names.

### `Governance(...)`

Validates all naming parts and builds names. Constructing it with an invalid value raises `GovernanceError`.

Parameters: `country`, `region`, `environment`, `layer`, `domain`, `subdomain` (all strings), and `data_product` (string, **gold layer only** — required for `gold`, must be omitted for `bronze`/`silver`).

Useful methods:
- `catalog_name()` returns the catalog string.
- `schema_name()` returns the schema string.
- `fqn(table_name)` returns the full three-part name for a given table.

### `DataClient(spark, governance)`

Writes and reads managed Delta tables using the names from a `Governance` object.

- `write_table(df, table_name, mode="overwrite", partition_cols=None, dynamic_partition_overwrite=False)` Validates the table name, creates the schema if it does not exist, writes the DataFrame as a managed Delta table, and returns the full name it wrote to. `mode` is `"overwrite"` or `"append"`. `partition_cols` is an optional list of column names to partition by. Set `dynamic_partition_overwrite=True` (with `mode="overwrite"`) to enable dynamic partition overwrite (`partitionOverwriteMode=dynamic`): only the partitions present in `df` are replaced, the rest are left untouched — useful for reprocessing a single `rate_date` without rewriting the whole table.
- `upsert_table(df, table_name, merge_keys, partition_cols=None)` Upserts the DataFrame into the table via a Delta `MERGE`: rows whose `merge_keys` match are updated, the rest are inserted. `merge_keys` is a column name or list of column names that uniquely identify a row (e.g. `["symbol", "rate_date"]`). The table is created on the first call (so it also works from scratch), and `partition_cols` is only applied on that first create. Returns the full name it wrote to.
- `read_table(table_name, filters=None)` Returns the table as a DataFrame, resolved to the project's full name. Pass `filters` to read only part of the table — when the filter is on a partition column this triggers **partition pruning**, so an incremental read scans only the matching partitions. `filters` can be:
  - a SQL string: `read_table("daily", "rate_date >= '2026-06-01'")`
  - a dict of column→value (equality): `read_table("daily", {"rate_date": "2026-06-17"})`
  - a list of conditions (AND-combined): `read_table("daily", ["rate_date >= '2026-06-01'", "symbol = 'BTCUSDT'"])`

## 7. Common errors

| Message you see                                          | Cause                                                              | Fix                                                        |
| -------------------------------------------------------- | ------------------------------------------------------------------ | ---------------------------------------------------------- |
| `'layer'='raw' is not allowed. Allowed: [...]`           | A controlled field uses a value outside the agreed list.           | Use one of the listed values.                              |
| `'domain'='market' is not allowed. Allowed: ['binance', ...]` | The domain is valid in another layer, but not this one.       | Use a domain allowed for the layer you chose (vocabulary is per layer). |
| `'subdomain (domain='binance')'='fear_greed' is not allowed` | The subdomain is valid, but not under that domain.             | Use a subdomain that belongs to the domain you chose.      |
| `'data_product' is required for the 'gold' layer`        | A gold `Governance` was built without a `data_product`.            | Pass a `data_product` when `layer="gold"`.                 |
| `'data_product' is not allowed for the 'bronze' layer`   | A `data_product` was passed to a bronze/silver `Governance`.        | Omit `data_product` for bronze/silver.                     |
| `'region'='Sa' is not valid lowercase snake_case`        | A free-form field has uppercase, spaces, or bad underscores.       | Use lowercase snake_case.                                  |
| `'data_product'='select' is a reserved word`             | A free-form field uses a reserved SQL word.                        | Pick a different name.                                     |
| `mode must be one of ('append', 'overwrite')`            | `write_table` got an unsupported mode.                             | Use `"overwrite"` or `"append"`.                           |
| `dynamic_partition_overwrite is only valid with mode='overwrite'` | The flag was passed with `mode="append"`.                | Use it only with `mode="overwrite"`.                       |
| `merge_keys must be a non-empty column name or list of names` | `upsert_table` got no merge keys.                            | Pass the key column(s), e.g. `["symbol", "rate_date"]`.    |
| `invalid merge key: ...`                                 | A merge key is not a plain column identifier.                      | Use simple column names (letters, digits, underscores).    |
| A Spark error on `CREATE SCHEMA`                          | The catalog does not exist yet.                                    | Ask the project owner to create the shared catalog first.  |

## 8. Good to know

- The catalog is created once by the project owner and shared. `zordon` creates the schema automatically but never the catalog.
- The allowed values live in `src/zordon/vocabularies.py` as `LAYERS`, `COUNTRIES`, `ENVIRONMENTS`, and the per-layer domain/subdomain dicts: `BRONZE_DOMAINS` / `BRONZE_SUBDOMAINS`, `SILVER_DOMAINS` / `SILVER_SUBDOMAINS`, `GOLD_DOMAINS` / `GOLD_SUBDOMAINS`. The bronze and silver context lists are kept in sync through a shared `_MARKET_CONTEXTS` dict. To add or change an allowed value, the project owner edits that one file and re-publishes the package (rebuild the wheel for Option C, or just re-sync for Options A/B).
- `zordon` only works with managed Delta tables. It does not handle external tables, permissions, or data-quality checks.
- Tests live in `tests/` and need no Spark session — run them with `pytest` (`pip install -e .[dev]` first, or `PYTHONPATH=src pytest`).
