"""
zordon
======

Tiny helper library for a student data-engineering project on Databricks.

Its only job: make every developer working on the project in parallel follow
the SAME naming rules for Unity Catalog (catalog / schema / table), and write
managed Delta tables to those names.

It is NOT installed on the cluster. Drop this file in the project's Workspace
folder (or Repo) and import it from a notebook.

Naming standard
---------------
    catalog : {prefix}_uc_{country}_{region}_{environment}   -> proj_uc_br_sa_dev
    schema  : {layer}_{domain}_{subdomain}_{data_product}    -> bronze_sales_crm_events_user_interaction
    table   : {table_name}                                   -> log
    fqn     : {catalog}.{schema}.{table_name}

Validation
----------
Controlled vocabulary (value must be a key in the dict below):
    layer, country, environment, domain, subdomain (per domain)
Free-form snake_case (format only):
    prefix, region, data_product, table_name
"""

import re

__all__ = [
    "Governance", "DataClient", "GovernanceError",
    "LAYERS", "COUNTRIES", "ENVIRONMENTS", "DOMAINS", "SUBDOMAINS",
]

# ---------------------------------------------------------------------------
# Controlled vocabularies — single shared source of truth.
# The project owner edits these once; everyone imports the same file.
# Keys are the allowed values; values are human-readable descriptions.
# Keys MUST be lowercase snake_case.
# ---------------------------------------------------------------------------

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

DOMAINS = {
    "sales":     "sales domain",
    "marketing": "marketing domain",
    "finance":   "finance domain",
}

# Nested: domain -> {subdomain: description}.
# Keys here must stay in sync with DOMAINS keys.
SUBDOMAINS = {
    "sales":     {"crm_events": "CRM event data", "orders": "order data"},
    "marketing": {"campaigns": "campaign data", "web_analytics": "web analytics data"},
    "finance":   {"exchanges": "exchange / FX data", "invoices": "invoice data"},
}


class GovernanceError(Exception):
    """Raised when a name part fails validation (vocabulary or format)."""
    pass


class Governance:
    """Validates the naming inputs and builds catalog / schema / FQN names.

    All parts are validated on construction, so an invalid Governance object
    can never be created.
    """

    # lowercase snake_case: letter first, single underscores only.
    _NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")

    # small reserved-word exclusion list for free-form fields.
    _RESERVED_WORDS = {
        "select", "from", "where", "table", "catalog", "schema", "database",
        "create", "drop", "insert", "update", "delete", "grant", "user",
        "order", "group", "by", "join", "on", "as",
    }

    def __init__(self, prefix, country, region, environment,
                 layer, domain, subdomain, data_product):
        self.prefix = prefix
        self.country = country
        self.region = region
        self.environment = environment
        self.layer = layer
        self.domain = domain
        self.subdomain = subdomain
        self.data_product = data_product

        # controlled vocabulary (domain before subdomain).
        self.validate_vocabulary(layer, LAYERS, "layer")
        self.validate_vocabulary(country, COUNTRIES, "country")
        self.validate_vocabulary(environment, ENVIRONMENTS, "environment")
        self.validate_vocabulary(domain, DOMAINS, "domain")
        self.validate_vocabulary(subdomain, SUBDOMAINS.get(domain, {}),
                                 f"subdomain (domain='{domain}')")

        # free-form format.
        self.validate_name(prefix, "prefix")
        self.validate_name(region, "region")
        self.validate_name(data_product, "data_product")

    def validate_vocabulary(self, value, allowed, label="name"):
        """Check that value is a key in the allow-list dict.
        Returns True or raises GovernanceError."""
        if value not in allowed:
            raise GovernanceError(
                f"'{label}'='{value}' is not allowed. "
                f"Allowed: {list(allowed.keys())}"
            )
        return True

    def validate_name(self, name, label="name"):
        """Format check for a free-form name part.
        Returns True or raises GovernanceError."""
        if not isinstance(name, str) or not name:
            raise GovernanceError(f"'{label}' must be a non-empty string, got: {name!r}")
        if not self._NAME_PATTERN.match(name):
            raise GovernanceError(
                f"'{label}'='{name}' is not valid lowercase snake_case "
                f"(allowed: ^[a-z][a-z0-9]*(_[a-z0-9]+)*$)"
            )
        if name in self._RESERVED_WORDS:
            raise GovernanceError(f"'{label}'='{name}' is a reserved word and cannot be used")
        return True

    def catalog_name(self):
        return f"{self.prefix}_uc_{self.country}_{self.region}_{self.environment}"

    def schema_name(self):
        return f"{self.layer}_{self.domain}_{self.subdomain}_{self.data_product}"

    def fqn(self, table_name):
        """Validate table_name (format), then build the 3-part FQN."""
        self.validate_name(table_name, "table_name")
        return f"{self.catalog_name()}.{self.schema_name()}.{table_name}"


class DataClient:
    """Reads/writes managed Delta tables using names from Governance.

    The catalog is assumed to already exist (created once by the project
    owner). This client only creates the schema if missing.
    """

    _VALID_MODES = ("append", "overwrite")

    def __init__(self, spark, governance):
        self.spark = spark
        self.governance = governance

    def write_table(self, df, table_name, mode="overwrite", partition_cols=None):
        """Validate the name, ensure the schema exists, and write a managed
        Delta table. Returns the FQN it wrote to."""
        if mode not in self._VALID_MODES:
            raise ValueError(f"mode must be one of {self._VALID_MODES}, got: {mode!r}")

        fqn = self.governance.fqn(table_name)
        catalog = self.governance.catalog_name()
        schema = self.governance.schema_name()

        self.spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{catalog}`.`{schema}`")

        writer = df.write.format("delta").mode(mode)
        if partition_cols:
            writer = writer.partitionBy(*partition_cols)
        writer.saveAsTable(fqn)
        return fqn

    def read_table(self, table_name):
        """Read a table by its short name, resolved to the project's FQN."""
        return self.spark.read.table(self.governance.fqn(table_name))
