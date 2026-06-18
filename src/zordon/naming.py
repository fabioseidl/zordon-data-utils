"""Identifier naming validation for catalogs, schemas and tables.

The rules are deliberately split into tiers, from hard technical limits to soft
organizational policy, so it is clear *why* a name is rejected:

  1. native    — Unity Catalog technical constraints (length, characters).
  2. format    — the project's strict snake_case convention.
  3. reserved  — SQL engine reserved words and system-reserved prefixes.
  4. governance— organizational rules (no manual versioning / env / suffixes).

``name_violation`` returns ``(tier, reason)`` for the first rule a name breaks
(or ``None`` if it is clean); ``validate_name`` raises ``GovernanceError`` with
that information, and ``is_valid_name`` is the boolean shortcut.
"""

import re

from .errors import GovernanceError

__all__ = [
    "validate_name", "is_valid_name", "name_violation",
    "MAX_NAME_LENGTH", "STRICT_SNAKE_CASE",
    "NATIVE_FORBIDDEN_CHARS", "SQL_RESERVED_WORDS",
    "SYSTEM_RESERVED_PREFIXES", "VERSIONING_SUFFIXES", "ENVIRONMENT_TERMS",
]

# --- Tier 1: native Unity Catalog technical constraints ---------------------
# Names are stored lowercase; length is capped and a few characters are illegal.
MAX_NAME_LENGTH = 255
# period, space and forward slash (ASCII control chars handled separately).
NATIVE_FORBIDDEN_CHARS = (".", " ", "/")
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_FORBIDDEN_CHAR_LABELS = {".": "'.'", " ": "space", "/": "'/'"}

# --- Tier 2: format convention (strict snake_case) --------------------------
# lowercase letters, digits and underscores, starting with a letter.
STRICT_SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")

# --- Tier 3: SQL engine reserved words + system-reserved prefixes ------------
SQL_RESERVED_WORDS = frozenset({
    # Spark / Databricks join & set-operation keywords.
    "anti", "cross", "except", "full", "inner", "intersect", "join",
    "lateral", "left", "mask", "minus", "natural", "on", "right", "semi",
    "union", "using", "null", "default", "true", "false",
    # common ANSI DML / DDL keywords that also break unquoted queries.
    "select", "from", "where", "table", "catalog", "schema", "database",
    "create", "drop", "insert", "update", "delete", "grant", "user",
    "order", "group", "by", "as",
})
# leading '_' is reserved for pseudo-columns / metadata (e.g. _metadata).
SYSTEM_RESERVED_PREFIXES = ("sys", "databricks")

# --- Tier 4: governance / organizational rules ------------------------------
# Manual versioning / temp terms, rejected as the last underscore-token.
VERSIONING_SUFFIXES = ("old", "new", "backup", "bkp", "temp", "tmp", "final")
# Environment terms, rejected as the first OR last token (isolate envs by
# catalog/schema, never inside the table name).
ENVIRONMENT_TERMS = ("test", "teste", "dev", "prod", "sandbox")
_VERSION_TOKEN = re.compile(r"^v[0-9]+$")     # _v1, _v2, ...
_TRAILING_NUMBER = re.compile(r"[0-9]$")      # any name ending in a digit


def _native_violation(name):
    if len(name) > MAX_NAME_LENGTH:
        return f"exceeds the {MAX_NAME_LENGTH}-character limit"
    for ch in NATIVE_FORBIDDEN_CHARS:
        if ch in name:
            return f"contains the forbidden character {_FORBIDDEN_CHAR_LABELS[ch]}"
    if _CONTROL_CHARS.search(name):
        return "contains an ASCII control character"
    return None


def _governance_violation(name):
    tokens = name.split("_")
    first, last = tokens[0], tokens[-1]
    if _VERSION_TOKEN.match(last):
        return (f"ends with the manual version indicator '{last}' "
                f"(use Delta Lake time travel instead)")
    if last in VERSIONING_SUFFIXES:
        return (f"ends with the forbidden suffix '_{last}' "
                f"(avoid manual versioning / temp names)")
    for term in ENVIRONMENT_TERMS:
        if first == term or last == term:
            return (f"contains the environment term '{term}' "
                    f"(isolate environments by catalog/schema, not table name)")
    if _TRAILING_NUMBER.search(name):
        return ("ends with a number "
                "(avoid manual partitioning / versioning in the name)")
    return None


def name_violation(name):
    """Return ``(tier, reason)`` for the first rule ``name`` breaks, else None.

    ``tier`` is one of ``"native"``, ``"format"``, ``"reserved"`` or
    ``"governance"``.
    """
    if not isinstance(name, str) or not name:
        return ("native", "must be a non-empty string")

    native = _native_violation(name)
    if native:
        return ("native", native)

    # leading '_' also fails snake_case, but report the precise reason.
    if name.startswith("_"):
        return ("reserved",
                "starts with '_' (reserved for metadata / pseudo-columns)")

    if not STRICT_SNAKE_CASE.match(name):
        return ("format",
                "is not strict snake_case (^[a-z][a-z0-9_]*$): use lowercase "
                "letters, digits and underscores, starting with a letter")

    # name is now guaranteed lowercase [a-z0-9_], starting with a letter.
    for prefix in SYSTEM_RESERVED_PREFIXES:
        if name.startswith(prefix):
            return ("reserved", f"starts with the reserved prefix '{prefix}'")

    if name in SQL_RESERVED_WORDS:
        return ("reserved", "is a SQL reserved word")

    governance = _governance_violation(name)
    if governance:
        return ("governance", governance)

    return None


def is_valid_name(name):
    """Return True if ``name`` passes every tier of validation."""
    return name_violation(name) is None


def validate_name(name, label="name"):
    """Validate one identifier (catalog / schema / table part).

    Returns True if valid, otherwise raises ``GovernanceError`` describing the
    failing rule and its tier.
    """
    violation = name_violation(name)
    if violation is None:
        return True
    tier, reason = violation
    raise GovernanceError(f"'{label}'='{name}' {reason} [{tier} rule]")
