from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from domain.inventory import InventoryEngine
from domain.ledger import EventLocation, EventOrigin, LedgerEvent, LedgerLeg
from tests.constants import BTC, EUR, SPOT_WALLET
from utils.tax_summary import TaxEventKind, compute_weekly_tax_summary, generate_tax_events

TEST_ORIGIN = EventOrigin(location=EventLocation.INTERNAL, external_id="tax-fixture")


def test_weekly_tax_summary_skips_tax_free_disposals(inventory_engine: InventoryEngine) -> None:
    events = [
        LedgerEvent(
            timestamp=datetime(2023, 1, 1, 12, tzinfo=timezone.utc),
            origin=TEST_ORIGIN,
            ingestion="manual_test",
            legs=[
                LedgerLeg(asset_id=BTC, quantity=Decimal("0.6"), account_chain_id=SPOT_WALLET),
                LedgerLeg(asset_id=EUR, quantity=Decimal("-6000"), account_chain_id=SPOT_WALLET),
            ],
        ),
        LedgerEvent(
            timestamp=datetime(2024, 12, 1, 12, tzinfo=timezone.utc),
            origin=TEST_ORIGIN,
            ingestion="manual_test",
            legs=[
                LedgerLeg(asset_id=BTC, quantity=Decimal("0.4"), account_chain_id=SPOT_WALLET),
                LedgerLeg(asset_id=EUR, quantity=Decimal("-12000"), account_chain_id=SPOT_WALLET),
            ],
        ),
        LedgerEvent(
            timestamp=datetime(2024, 12, 15, 12, tzinfo=timezone.utc),
            origin=TEST_ORIGIN,
            ingestion="manual_test",
            legs=[
                LedgerLeg(asset_id=BTC, quantity=Decimal("-0.3"), account_chain_id=SPOT_WALLET),
                LedgerLeg(asset_id=EUR, quantity=Decimal("9000"), account_chain_id=SPOT_WALLET),
            ],
        ),
        LedgerEvent(
            timestamp=datetime(2025, 1, 10, 12, tzinfo=timezone.utc),
            origin=TEST_ORIGIN,
            ingestion="manual_test",
            legs=[
                LedgerLeg(asset_id=BTC, quantity=Decimal("-0.4"), account_chain_id=SPOT_WALLET),
                LedgerLeg(asset_id=EUR, quantity=Decimal("16000"), account_chain_id=SPOT_WALLET),
            ],
        ),
        LedgerEvent(
            timestamp=datetime(2025, 1, 17, 12, tzinfo=timezone.utc),
            origin=TEST_ORIGIN,
            ingestion="manual_test",
            legs=[
                LedgerLeg(asset_id=BTC, quantity=Decimal("-0.2"), account_chain_id=SPOT_WALLET),
                LedgerLeg(asset_id=EUR, quantity=Decimal("10000"), account_chain_id=SPOT_WALLET),
            ],
        ),
    ]

    result = inventory_engine.process(events)
    tax_events = generate_tax_events(result, events)
    assert len(tax_events) == 2
    assert all(event.kind == TaxEventKind.DISPOSAL for event in tax_events)
    taxable_link_ids = {event.source_id for event in tax_events}
    expected_taxable_links = {link.id for link in result.disposal_links if link.lot_id == result.acquisition_lots[1].id}
    assert taxable_link_ids == expected_taxable_links
    summaries = compute_weekly_tax_summary(tax_events, result, events)
    by_week = {summary.week_start: summary for summary in summaries}

    assert date(2024, 12, 9) not in by_week

    week_one_start = date(2025, 1, 6)
    week_one = by_week[week_one_start]
    assert week_one.taxable_events == 1
    assert week_one.proceeds == Decimal("4000")
    assert week_one.cost_basis == Decimal("3000")
    assert week_one.taxable_gain == Decimal("1000")

    week_two_start = date(2025, 1, 13)
    week_two = by_week[week_two_start]
    assert week_two.taxable_events == 1
    assert week_two.proceeds == Decimal("10000")
    assert week_two.cost_basis == Decimal("6000")
    assert week_two.taxable_gain == Decimal("4000")

    assert [summary.week_start for summary in summaries] == sorted(by_week)
