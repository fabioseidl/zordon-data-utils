"""Naming governance: validate the inputs and build catalog / schema / FQN names."""

import re

from .errors import GovernanceError
from .vocabularies import (
    LAYERS, COUNTRIES, ENVIRONMENTS, DOMAIN_VOCAB_BY_LAYER,
)

__all__ = ["Governance"]


class Governance:
    """Validates the naming inputs and builds catalog / schema / FQN names.

    All parts are validated on construction, so an invalid Governance object
    can never be created.

    The catalog / schema naming standard:

        catalog : {prefix}_uc_{country}_{region}_{environment}
        schema  : bronze/silver -> {layer}_{domain}_{subdomain}
                  gold          -> {layer}_{domain}_{subdomain}_{data_product}
        fqn     : {catalog}.{schema}.{table_name}

    The domain/subdomain vocabulary is layer-dependent (see ``vocabularies``):
    bronze is by source, silver by context, gold by business product. The
    ``data_product`` is gold-only (required there, forbidden elsewhere).
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
                 layer, domain, subdomain, data_product=None):
        self.prefix = prefix
        self.country = country
        self.region = region
        self.environment = environment
        self.layer = layer
        self.domain = domain
        self.subdomain = subdomain
        self.data_product = data_product

        # controlled vocabulary (layer first, then domain before subdomain).
        self.validate_vocabulary(layer, LAYERS, "layer")
        self.validate_vocabulary(country, COUNTRIES, "country")
        self.validate_vocabulary(environment, ENVIRONMENTS, "environment")

        # domain/subdomain use a different vocabulary per layer:
        #   bronze -> by source   (BRONZE_DOMAINS / BRONZE_SUBDOMAINS)
        #   silver -> by context  (SILVER_DOMAINS / SILVER_SUBDOMAINS)
        #   gold   -> by product  (GOLD_DOMAINS / GOLD_SUBDOMAINS)
        # (layer is already validated above, so the lookup always succeeds.)
        domains, subdomains = DOMAIN_VOCAB_BY_LAYER[layer]
        self.validate_vocabulary(domain, domains, "domain")
        self.validate_vocabulary(subdomain, subdomains.get(domain, {}),
                                 f"subdomain (domain='{domain}')")

        # free-form format.
        self.validate_name(prefix, "prefix")
        self.validate_name(region, "region")

        # data_product belongs to the gold layer only. Bronze/silver schemas
        # are named by source (domain) and context (subdomain) alone.
        if layer == "gold":
            if not data_product:
                raise GovernanceError(
                    "'data_product' is required for the 'gold' layer"
                )
            self.validate_name(data_product, "data_product")
        elif data_product is not None:
            raise GovernanceError(
                f"'data_product' is not allowed for the '{layer}' layer "
                f"(only the 'gold' layer uses it)"
            )

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
        # Bronze/silver: source + context only. Gold: adds the data_product.
        if self.layer == "gold":
            return f"{self.layer}_{self.domain}_{self.subdomain}_{self.data_product}"
        return f"{self.layer}_{self.domain}_{self.subdomain}"

    def fqn(self, table_name):
        """Validate table_name (format), then build the 3-part FQN."""
        self.validate_name(table_name, "table_name")
        return f"{self.catalog_name()}.{self.schema_name()}.{table_name}"
