from datetime import datetime, timezone
from decimal import Decimal

import pytest

from accounts import KRAKEN_ACCOUNT_ID
from corrections.ingestion import ledger_event_from_correction
from domain.acquisition_disposal.price_override_resolution import (
    PriceOverrideResolutionError,
    build_override_rates_by_event_origin,
)
from domain.correction import LedgerCorrection
from domain.ledger import AssetId, EventLocation, EventOrigin, LedgerEvent, LedgerLeg
from domain.price_override import PriceOverride
from tests.constants import BTC, ETH, LEDGER_WALLET

_TS = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)


def _origin(external_id: str) -> EventOrigin:
    return EventOrigin(location=EventLocation.ETHEREUM, external_id=external_id)


def _event(external_id: str, *asset_ids: AssetId) -> LedgerEvent:
    return LedgerEvent(
        timestamp=_TS,
        event_origin=_origin(external_id),
        ingestion="raw_ingestion",
        legs=[LedgerLeg(asset_id=asset, quantity=Decimal("1"), account_chain_id=LEDGER_WALLET) for asset in asset_ids],
    )


def _replacement(*sources: str) -> tuple[LedgerCorrection, LedgerEvent]:
    correction = LedgerCorrection(
        timestamp=_TS,
        sources=frozenset(_origin(source) for source in sources),
        legs=frozenset([LedgerLeg(asset_id=ETH, quantity=Decimal("1"), account_chain_id=KRAKEN_ACCOUNT_ID)]),
    )
    return correction, ledger_event_from_correction(correction)


def _override(*, sources: set[EventOrigin], asset_id: AssetId = ETH, rate_eur: str = "1500") -> PriceOverride:
    return PriceOverride(sources=frozenset(sources), asset_id=asset_id, rate_eur=Decimal(rate_eur))


def test_resolves_override_on_passthrough_event() -> None:
    event = _event("0xpass", ETH)
    override = _override(sources={_origin("0xpass")})

    resolved = build_override_rates_by_event_origin([event], [], [override])

    assert resolved == {event.event_origin: {ETH: Decimal("1500")}}


def test_resolves_override_matching_replacement_source_set() -> None:
    correction, synthetic = _replacement("0xraw")
    override = _override(sources={_origin("0xraw")})

    resolved = build_override_rates_by_event_origin([synthetic], [correction], [override])

    assert synthetic.event_origin.location == EventLocation.INTERNAL
    assert resolved == {synthetic.event_origin: {ETH: Decimal("1500")}}


def test_resolves_override_matching_merged_replacement_source_set() -> None:
    correction, synthetic = _replacement("0xraw1", "0xraw2")
    override = _override(sources={_origin("0xraw1"), _origin("0xraw2")})

    resolved = build_override_rates_by_event_origin([synthetic], [correction], [override])

    assert resolved == {synthetic.event_origin: {ETH: Decimal("1500")}}


def test_override_is_orphaned_when_its_event_is_regrouped_into_a_larger_replacement() -> None:
    # Override authored against raw event {0xraw1}; a correction later merges {0xraw1, 0xraw2}.
    correction, synthetic = _replacement("0xraw1", "0xraw2")
    override = _override(sources={_origin("0xraw1")})

    with pytest.raises(PriceOverrideResolutionError, match="sources do not match any corrected event"):
        build_override_rates_by_event_origin([synthetic], [correction], [override])


def test_multiple_overrides_price_distinct_assets_of_one_event() -> None:
    event = _event("0xswap", ETH, BTC)
    resolved = build_override_rates_by_event_origin(
        [event],
        [],
        [
            _override(sources={_origin("0xswap")}, asset_id=ETH, rate_eur="1500"),
            _override(sources={_origin("0xswap")}, asset_id=BTC, rate_eur="40000"),
        ],
    )

    assert resolved == {event.event_origin: {ETH: Decimal("1500"), BTC: Decimal("40000")}}


def test_unresolved_source_is_a_problem() -> None:
    override = _override(sources={_origin("0xghost")})

    with pytest.raises(PriceOverrideResolutionError, match="sources do not match any corrected event"):
        build_override_rates_by_event_origin([_event("0xother", ETH)], [], [override])


def test_source_claimed_by_discard_is_a_problem() -> None:
    discard = LedgerCorrection(timestamp=_TS, sources=frozenset([_origin("0xdiscarded")]))
    override = _override(sources={_origin("0xdiscarded")})

    with pytest.raises(PriceOverrideResolutionError, match="sources do not match any corrected event"):
        build_override_rates_by_event_origin([], [discard], [override])


def test_sources_spanning_two_events_is_a_problem() -> None:
    override = _override(sources={_origin("0xone"), _origin("0xtwo")})

    with pytest.raises(PriceOverrideResolutionError, match="sources do not match any corrected event"):
        build_override_rates_by_event_origin([_event("0xone", ETH), _event("0xtwo", ETH)], [], [override])


def test_asset_not_in_resolved_event_is_a_problem() -> None:
    override = _override(sources={_origin("0xpass")}, asset_id=BTC)

    with pytest.raises(PriceOverrideResolutionError, match="asset is not present in resolved event"):
        build_override_rates_by_event_origin([_event("0xpass", ETH)], [], [override])


def test_conflicting_overrides_on_same_event_and_asset_is_a_problem() -> None:
    event = _event("0xpass", ETH)
    overrides = [
        _override(sources={_origin("0xpass")}, asset_id=ETH, rate_eur="1500"),
        _override(sources={_origin("0xpass")}, asset_id=ETH, rate_eur="1600"),
    ]

    with pytest.raises(PriceOverrideResolutionError, match="conflicts with another override"):
        build_override_rates_by_event_origin([event], [], overrides)


def test_all_problems_are_reported_together() -> None:
    overrides = [
        _override(sources={_origin("0xghost")}),
        _override(sources={_origin("0xpass")}, asset_id=BTC),
    ]

    with pytest.raises(PriceOverrideResolutionError) as exc_info:
        build_override_rates_by_event_origin([_event("0xpass", ETH)], [], overrides)

    assert len(exc_info.value.problems) == 2
