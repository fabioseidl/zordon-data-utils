"""Exceptions raised by zordon."""

__all__ = ["GovernanceError"]


class GovernanceError(Exception):
    """Raised when a name part fails validation (vocabulary or format)."""
    pass
