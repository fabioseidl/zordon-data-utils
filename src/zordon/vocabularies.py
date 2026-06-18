"""Controlled vocabularies — the single shared source of truth for naming.

The project owner edits these dictionaries once; because everyone imports the
same installed package (or the same file), everyone gets the same allowed
values. Keys are the allowed values; values are human-readable descriptions.
Keys MUST be lowercase snake_case, otherwise the generated catalog/schema names
would be invalid.

The domain/subdomain vocabulary is layer-dependent, because each medallion
layer is organised by a different principle:
    bronze -> by SOURCE   (one schema per exchange/provider + context)
    silver -> by CONTEXT  (sources merged/conformed, one schema per entity)
    gold   -> by PRODUCT  (business/analytical product + data_product)
"""

__all__ = [
    "LAYERS", "COUNTRIES", "ENVIRONMENTS",
    "BRONZE_DOMAINS", "BRONZE_SUBDOMAINS",
    "SILVER_DOMAINS", "SILVER_SUBDOMAINS",
    "GOLD_DOMAINS", "GOLD_SUBDOMAINS",
    "DOMAIN_VOCAB_BY_LAYER",
]

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

# Contexts (entities) that exist for market data. Defined once so the bronze
# (per source) and silver (conformed) vocabularies stay in sync.
_MARKET_CONTEXTS = {
    "ohlcv":   "OHLCV candles (open/high/low/close/volume)",
    "symbols": "trading pairs / instrument reference",
    "tickers": "24h ticker statistics",
    "orders":  "order / trade data",
}

# --- Bronze: organised by SOURCE --------------------------------------------
# Domain = the data SOURCE (the exchange / provider we ingest from);
# subdomain = the CONTEXT landed from that source.
BRONZE_DOMAINS = {
    "binance":        "Binance Spot API (price & volume / OHLCV)",
    "poloniex":       "Poloniex Spot API (price & volume / OHLCV)",
    "alternative_me": "Alternative.me (Fear & Greed Index / sentiment)",
}

# Nested: domain -> {subdomain: description}. Keys must stay in sync with
# BRONZE_DOMAINS keys.
BRONZE_SUBDOMAINS = {
    "binance":        dict(_MARKET_CONTEXTS),
    "poloniex":       dict(_MARKET_CONTEXTS),
    "alternative_me": {"fear_greed": "Fear & Greed Index sentiment readings"},
}

# --- Silver: organised by CONTEXT (conformed across sources) -----------------
# The same data from all exchanges is merged by context, so the source drops
# out of the name. Domain = conformed area; subdomain = the entity/context.
# The originating exchange is kept as a column in the data, not in the name.
SILVER_DOMAINS = {
    "market":    "market data conformed/merged across all exchanges",
    "sentiment": "market sentiment conformed across sources",
}

# Nested: domain -> {subdomain: description}. Keys must stay in sync with
# SILVER_DOMAINS keys.
SILVER_SUBDOMAINS = {
    "market":    dict(_MARKET_CONTEXTS),
    "sentiment": {"fear_greed": "Fear & Greed Index sentiment readings"},
}

# --- Gold: organised by BUSINESS / DATA PRODUCT -----------------------------
# In gold the domain/subdomain no longer describe where data came from; they
# describe the business product built on top of the conformed data. The
# free-form data_product completes the name. Example:
#   domain="finance", subdomain="investments", data_product="market_analysis"
GOLD_DOMAINS = {
    "finance": "finance / market analytics domain",
}

# Nested: gold_domain -> {gold_subdomain: description}. Keys must stay in sync
# with GOLD_DOMAINS keys.
GOLD_SUBDOMAINS = {
    "finance": {
        "investments": "asset performance, risk & correlation analytics",
        "sentiment":   "market sentiment analytics (Fear & Greed integration)",
    },
}

# Layer -> (domains, subdomains) vocabulary. Used to pick the right allow-list.
DOMAIN_VOCAB_BY_LAYER = {
    "bronze": (BRONZE_DOMAINS, BRONZE_SUBDOMAINS),
    "silver": (SILVER_DOMAINS, SILVER_SUBDOMAINS),
    "gold":   (GOLD_DOMAINS, GOLD_SUBDOMAINS),
}
