from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from domain.inventory import InventoryEngine
from domain.ledger import EventLocation, EventOrigin, EventType, LedgerEvent, LedgerLeg
from tests.helpers.test_price_service import TestPriceService
from utils.tax_summary import TaxEventKind, compute_weekly_tax_summary, generate_tax_events

TEST_ORIGIN = EventOrigin(location=EventLocation.INTERNAL, external_id="tax-fixture")


def test_weekly_tax_summary_skips_tax_free_disposals() -> None:
    price_service = TestPriceService()
    engine = InventoryEngine(price_provider=price_service)

    events = [
        LedgerEvent(
            timestamp=datetime(2023, 1, 1, 12, tzinfo=timezone.utc),
            origin=TEST_ORIGIN,
            ingestion="manual_test",
            event_type=EventType.TRADE,
            legs=[
                LedgerLeg(asset_id="BTC", quantity=Decimal("0.6"), wallet_id="spot"),
                LedgerLeg(asset_id="EUR", quantity=Decimal("-6000"), wallet_id="spot"),
            ],
        ),
        LedgerEvent(
            timestamp=datetime(2024, 12, 1, 12, tzinfo=timezone.utc),
            origin=TEST_ORIGIN,
            ingestion="manual_test",
            event_type=EventType.TRADE,
            legs=[
                LedgerLeg(asset_id="BTC", quantity=Decimal("0.4"), wallet_id="spot"),
                LedgerLeg(asset_id="EUR", quantity=Decimal("-12000"), wallet_id="spot"),
            ],
        ),
        LedgerEvent(
            timestamp=datetime(2024, 12, 15, 12, tzinfo=timezone.utc),
            origin=TEST_ORIGIN,
            ingestion="manual_test",
            event_type=EventType.TRADE,
            legs=[
                LedgerLeg(asset_id="BTC", quantity=Decimal("-0.3"), wallet_id="spot"),
                LedgerLeg(asset_id="EUR", quantity=Decimal("9000"), wallet_id="spot"),
            ],
        ),
        LedgerEvent(
            timestamp=datetime(2025, 1, 10, 12, tzinfo=timezone.utc),
            origin=TEST_ORIGIN,
            ingestion="manual_test",
            event_type=EventType.TRADE,
            legs=[
                LedgerLeg(asset_id="BTC", quantity=Decimal("-0.4"), wallet_id="spot"),
                LedgerLeg(asset_id="EUR", quantity=Decimal("16000"), wallet_id="spot"),
            ],
        ),
        LedgerEvent(
            timestamp=datetime(2025, 1, 17, 12, tzinfo=timezone.utc),
            origin=TEST_ORIGIN,
            ingestion="manual_test",
            event_type=EventType.TRADE,
            legs=[
                LedgerLeg(asset_id="BTC", quantity=Decimal("-0.2"), wallet_id="spot"),
                LedgerLeg(asset_id="EUR", quantity=Decimal("10000"), wallet_id="spot"),
            ],
        ),
    ]

    result = engine.process(events)
    tax_events = generate_tax_events(result, events, tax_free_days=365)
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


def test_reward_acquisitions_are_taxed_when_received() -> None:
    price_service = TestPriceService()
    engine = InventoryEngine(price_provider=price_service)

    reward_time = datetime(2024, 5, 1, 12, tzinfo=timezone.utc)
    reward_quantity = Decimal("2.5")
    reward_leg = LedgerLeg(asset_id="ATOM", quantity=reward_quantity, wallet_id="earn")
    events = [
        LedgerEvent(
            timestamp=reward_time,
            origin=TEST_ORIGIN,
            ingestion="manual_test",
            event_type=EventType.REWARD,
            legs=[reward_leg],
        )
    ]

    result = engine.process(events)
    tax_events = generate_tax_events(result, events, tax_free_days=365)

    assert len(tax_events) == 1
    reward_tax = tax_events[0]
    assert reward_tax.kind == TaxEventKind.REWARD

    expected_rate = price_service.rate("ATOM", "EUR", reward_time)
    expected_proceeds = reward_quantity * expected_rate

    assert reward_tax.taxable_gain == expected_proceeds

    weekly = compute_weekly_tax_summary(tax_events, result, events)
    assert len(weekly) == 1
    summary = weekly[0]
    assert summary.week_start == date(2024, 4, 29)
    assert summary.week_end == date(2024, 5, 5)
    assert summary.taxable_events == 1
    assert summary.proceeds == expected_proceeds
    assert summary.cost_basis == Decimal("0")
    assert summary.taxable_gain == expected_proceeds
