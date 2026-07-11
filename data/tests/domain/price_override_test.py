from datetime import datetime, timezone
from decimal import Decimal

import pytest

from accounts import KRAKEN_ACCOUNT_ID
from corrections.ingestion import ledger_event_from_correction
from domain.correction import LedgerCorrection
from domain.ledger import AssetId, EventLocation, EventOrigin, LedgerEvent, LedgerLeg
from domain.price_override import (
    PriceOverride,
    PriceOverrideDraft,
    PriceOverrideValidationError,
    validate_overrides,
)
from tests.constants import BTC, ETH, LEDGER_WALLET

_TS = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)


def _origin(external_id: str, *, location: EventLocation = EventLocation.ETHEREUM) -> EventOrigin:
    return EventOrigin(location=location, external_id=external_id)


def _event(external_id: str, *asset_ids: AssetId) -> LedgerEvent:
    return LedgerEvent(
        timestamp=_TS,
        event_origin=_origin(external_id),
        ingestion="raw_ingestion",
        legs=[LedgerLeg(asset_id=asset, quantity=Decimal("1"), account_chain_id=LEDGER_WALLET) for asset in asset_ids],
    )


def _replacement(*sources: str) -> LedgerEvent:
    correction = LedgerCorrection(
        timestamp=_TS,
        sources=frozenset(_origin(source) for source in sources),
        legs=frozenset([LedgerLeg(asset_id=ETH, quantity=Decimal("1"), account_chain_id=KRAKEN_ACCOUNT_ID)]),
    )
    return ledger_event_from_correction(correction)


def _override(*, event_origin: EventOrigin, asset_id: AssetId = ETH, rate_eur: str = "1500") -> PriceOverride:
    return PriceOverride(event_origin=event_origin, asset_id=asset_id, rate_eur=Decimal(rate_eur))


def test_price_override_accepts_internal_synthetic_origin() -> None:
    # A replacement's corrected event is identified by its synthetic (INTERNAL, correction.id)
    # origin, so pricing one is a legitimate target -- unlike correction sources, which are raw-only.
    override = _override(event_origin=_origin("some-correction-uuid", location=EventLocation.INTERNAL))

    assert override.event_origin.location == EventLocation.INTERNAL


def test_price_override_rejects_non_positive_rate() -> None:
    with pytest.raises(ValueError, match="greater than 0"):
        _override(event_origin=_origin("0xabc"), rate_eur="0")

    with pytest.raises(ValueError, match="greater than 0"):
        _override(event_origin=_origin("0xabc"), rate_eur="-5")


def test_price_override_draft_has_no_id_and_override_generates_one() -> None:
    draft = PriceOverrideDraft(event_origin=_origin("0xabc"), asset_id=ETH, rate_eur=Decimal("1500"))
    assert not hasattr(draft, "id")

    assert _override(event_origin=_origin("0xabc")).id is not None


def test_override_on_passthrough_event_validates() -> None:
    event = _event("0xpass", ETH)

    validate_overrides([event], [_override(event_origin=event.event_origin)])


def test_override_on_replacement_synthetic_origin_validates() -> None:
    synthetic = _replacement("0xraw1", "0xraw2")

    validate_overrides([synthetic], [_override(event_origin=synthetic.event_origin)])

    assert synthetic.event_origin.location == EventLocation.INTERNAL


def test_override_is_orphaned_when_its_raw_event_is_folded_into_a_replacement() -> None:
    # Override authored against raw event 0xraw1; a correction later folds it into a replacement,
    # so the raw origin no longer appears among the corrected events.
    synthetic = _replacement("0xraw1", "0xraw2")
    override = _override(event_origin=_origin("0xraw1"))

    with pytest.raises(PriceOverrideValidationError, match="does not match any corrected event"):
        validate_overrides([synthetic], [override])


def test_origin_matching_no_corrected_event_is_a_problem() -> None:
    override = _override(event_origin=_origin("0xghost"))

    with pytest.raises(PriceOverrideValidationError, match="does not match any corrected event"):
        validate_overrides([_event("0xother", ETH)], [override])


def test_asset_absent_from_the_targeted_event_is_a_problem() -> None:
    event = _event("0xpass", ETH)
    override = _override(event_origin=event.event_origin, asset_id=BTC)

    with pytest.raises(PriceOverrideValidationError, match="absent from the legs of its corrected event"):
        validate_overrides([event], [override])


def test_problem_names_the_override_asset_and_targeted_origin() -> None:
    override = _override(event_origin=_origin("0xghost"), asset_id=BTC)

    with pytest.raises(PriceOverrideValidationError) as exc_info:
        validate_overrides([], [override])

    problem = exc_info.value.problems[0]
    assert str(override.id) in problem
    assert BTC in problem
    assert str(override.event_origin) in problem


def test_all_problems_are_reported_together() -> None:
    event = _event("0xpass", ETH)
    overrides = [
        _override(event_origin=_origin("0xghost")),
        _override(event_origin=event.event_origin, asset_id=BTC),
    ]

    with pytest.raises(PriceOverrideValidationError) as exc_info:
        validate_overrides([event], overrides)

    assert len(exc_info.value.problems) == 2
