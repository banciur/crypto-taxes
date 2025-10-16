"""Domain models and types for the crypto taxes engine.

This package contains in-memory (Pydantic) models describing the ledger and
inventory structures. They are independent from persistence models so that
business logic and testing can evolve without DB coupling.
"""

__all__ = [
    "ledger",
    "pricing",
]
