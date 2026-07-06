from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel

from domain.ledger import EventLocation, EventOrigin


def reject_duplicate_items(value: Any, *, item_model: type[BaseModel], field_name: str) -> Any:
    """Reject duplicate items so a set-typed field fails loudly instead of silently deduping.

    Meant to be called from a pydantic ``mode="before"`` field validator, without it, pydantic
    coerces a list/tuple that repeats an item into a set and drops the duplicate without complaint.
    """
    if not isinstance(value, (list, tuple)):
        return value
    normalized = [item_model.model_validate(item) for item in value]
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{field_name} must not contain duplicates")
    return value


def reject_internal_origins(origins: Iterable[EventOrigin], *, field_name: str = "sources") -> None:
    if any(origin.location == EventLocation.INTERNAL for origin in origins):
        raise ValueError(f"{field_name} must not contain INTERNAL origins")
