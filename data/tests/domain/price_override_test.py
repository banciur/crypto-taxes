from decimal import Decimal

import pytest

from domain.ledger import AssetId, EventLocation, EventOrigin
from domain.price_override import PriceOverride, PriceOverrideDraft
from tests.constants import ETH


def _origin(external_id: str, *, location: EventLocation = EventLocation.ETHEREUM) -> EventOrigin:
    return EventOrigin(location=location, external_id=external_id)


def test_price_override_normalizes_asset_id_upper_case() -> None:
    override = PriceOverride(
        sources=frozenset([_origin("0xabc")]),
        asset_id=AssetId("eth"),
        rate_eur=Decimal("1500"),
    )

    assert override.asset_id == ETH


def test_price_override_requires_at_least_one_source() -> None:
    with pytest.raises(ValueError, match="requires at least one source"):
        PriceOverride(sources=frozenset(), asset_id=ETH, rate_eur=Decimal("1"))


def test_price_override_rejects_internal_source_origin() -> None:
    with pytest.raises(ValueError, match="must not contain INTERNAL origins"):
        PriceOverride(
            sources=frozenset([_origin("some-uuid", location=EventLocation.INTERNAL)]),
            asset_id=ETH,
            rate_eur=Decimal("1"),
        )


def test_price_override_rejects_non_positive_rate() -> None:
    with pytest.raises(ValueError, match="rate_eur must be positive"):
        PriceOverride(sources=frozenset([_origin("0xabc")]), asset_id=ETH, rate_eur=Decimal("0"))

    with pytest.raises(ValueError, match="rate_eur must be positive"):
        PriceOverride(sources=frozenset([_origin("0xabc")]), asset_id=ETH, rate_eur=Decimal("-5"))


def test_price_override_rejects_duplicate_sources() -> None:
    with pytest.raises(ValueError, match="must not contain duplicates"):
        PriceOverrideDraft.model_validate(
            {
                "sources": [
                    {"location": "ETHEREUM", "external_id": "0xabc"},
                    {"location": "ETHEREUM", "external_id": "0xabc"},
                ],
                "asset_id": "ETH",
                "rate_eur": "1",
            }
        )


def test_price_override_draft_has_no_id_and_override_generates_one() -> None:
    draft = PriceOverrideDraft(sources=frozenset([_origin("0xabc")]), asset_id=ETH, rate_eur=Decimal("1500"))
    assert not hasattr(draft, "id")

    override = PriceOverride(sources=frozenset([_origin("0xabc")]), asset_id=ETH, rate_eur=Decimal("1500"))
    assert override.id is not None
