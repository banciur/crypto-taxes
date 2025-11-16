from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Tuple

from domain.inventory import InventoryEngine, InventoryResult
from domain.ledger import EventType, LedgerEvent, LedgerLeg


class StubPriceProvider:
    def __init__(self, rates: Dict[Tuple[str, str, datetime], Decimal]) -> None:
        self._rates = rates
        self.requests: List[Tuple[str, str, datetime]] = []

    def rate(self, base_id: str, quote_id: str, timestamp: datetime) -> Decimal:
        key = (base_id, quote_id, timestamp)
        self.requests.append(key)
        try:
            return self._rates[key]
        except KeyError as exc:
            raise AssertionError(f"No price for {key}") from exc


def test_inventory_engine_fifo_with_explicit_eur_legs() -> None:
    provider = StubPriceProvider({})
    engine = InventoryEngine(price_provider=provider)

    wallet_id = "hot_mm"

    t1 = datetime(2024, 9, 2, 12, 0, tzinfo=timezone.utc)
    t2 = datetime(2024, 9, 3, 12, 0, tzinfo=timezone.utc)
    t3 = datetime(2024, 9, 10, 12, 0, tzinfo=timezone.utc)

    buy1 = LedgerEvent(
        timestamp=t1,
        event_type=EventType.TRADE,
        legs=[
            LedgerLeg(asset_id="ETH", quantity=Decimal("1.0"), wallet_id=wallet_id),
            LedgerLeg(asset_id="EUR", quantity=Decimal("-3000"), wallet_id=wallet_id),
        ],
    )

    buy2 = LedgerEvent(
        timestamp=t2,
        event_type=EventType.TRADE,
        legs=[
            LedgerLeg(asset_id="ETH", quantity=Decimal("0.5"), wallet_id=wallet_id),
            LedgerLeg(asset_id="EUR", quantity=Decimal("-1500"), wallet_id=wallet_id),
        ],
    )

    sell1 = LedgerEvent(
        timestamp=t3,
        event_type=EventType.TRADE,
        legs=[
            LedgerLeg(asset_id="ETH", quantity=Decimal("-0.6"), wallet_id=wallet_id),
            LedgerLeg(asset_id="EUR", quantity=Decimal("2040"), wallet_id=wallet_id),
        ],
    )

    result: InventoryResult = engine.process([buy1, buy2, sell1])

    assert len(result.acquisition_lots) == 2
    assert all(lot.cost_eur_per_unit == Decimal("3000") for lot in result.acquisition_lots)

    assert len(result.disposal_links) == 1
    disposal_link = result.disposal_links[0]
    assert disposal_link.quantity_used == Decimal("0.6")
    assert disposal_link.proceeds_total_eur == Decimal("2040")

    assert [snap.quantity_remaining for snap in result.open_inventory] == [
        Decimal("0.4"),
        Decimal("0.5"),
    ]
    assert provider.requests == []


def test_inventory_engine_uses_price_provider_when_no_eur_leg() -> None:
    t1 = datetime(2024, 10, 1, 8, 0, tzinfo=timezone.utc)
    t2 = datetime(2024, 10, 5, 10, 0, tzinfo=timezone.utc)

    provider = StubPriceProvider(
        {
            ("BTC", "EUR", t1): Decimal("20000"),
            ("BTC", "EUR", t2): Decimal("21000"),
        }
    )
    engine = InventoryEngine(price_provider=provider)

    wallet_id = "treasury"

    airdrop = LedgerEvent(
        timestamp=t1,
        event_type=EventType.TRADE,
        legs=[
            LedgerLeg(asset_id="BTC", quantity=Decimal("2.0"), wallet_id=wallet_id),
        ],
    )

    payout = LedgerEvent(
        timestamp=t2,
        event_type=EventType.TRADE,
        legs=[
            LedgerLeg(asset_id="BTC", quantity=Decimal("-1.5"), wallet_id=wallet_id),
        ],
    )

    result = engine.process([airdrop, payout])

    assert len(result.acquisition_lots) == 1
    assert result.acquisition_lots[0].cost_eur_per_unit == Decimal("20000")

    assert len(result.disposal_links) == 1
    disposal = result.disposal_links[0]
    assert disposal.quantity_used == Decimal("1.5")
    assert disposal.proceeds_total_eur == Decimal("31500")  # 1.5 * 21000

    assert len(result.open_inventory) == 1
    remaining_snapshot = result.open_inventory[0]
    assert remaining_snapshot.quantity_remaining == Decimal("0.5")

    assert provider.requests == [
        ("BTC", "EUR", t1),
        ("BTC", "EUR", t2),
    ]


def test_third_asset_fee_leg_creates_disposal() -> None:
    timestamp = datetime(2024, 10, 1, 12, 0, tzinfo=timezone.utc)
    provider = StubPriceProvider(
        {
            ("LINK", "EUR", timestamp): Decimal("10"),
            ("WBTC", "EUR", timestamp): Decimal("20000"),
            ("ETH", "EUR", timestamp): Decimal("1500"),
        }
    )
    engine = InventoryEngine(price_provider=provider)
    wallet = "dex"

    link_reward = LedgerEvent(
        timestamp=timestamp,
        event_type=EventType.REWARD,
        legs=[
            LedgerLeg(asset_id="LINK", quantity=Decimal("5"), wallet_id=wallet),
        ],
    )

    ethtx = LedgerEvent(
        timestamp=timestamp,
        event_type=EventType.TRADE,
        legs=[
            LedgerLeg(asset_id="ETH", quantity=Decimal("1"), wallet_id=wallet),
            LedgerLeg(asset_id="EUR", quantity=Decimal("-1500"), wallet_id=wallet),
        ],
    )

    swap_event = LedgerEvent(
        timestamp=timestamp,
        event_type=EventType.TRADE,
        legs=[
            LedgerLeg(asset_id="ETH", quantity=Decimal("-1"), wallet_id=wallet),
            LedgerLeg(asset_id="WBTC", quantity=Decimal("0.05"), wallet_id=wallet),
            LedgerLeg(asset_id="LINK", quantity=Decimal("-2"), wallet_id=wallet),
        ],
    )

    result = engine.process([link_reward, ethtx, swap_event])

    assert len(result.disposal_links) == 2  # ETH disposal + LINK fee disposal
    fee_disposal = next(link for link in result.disposal_links if link.quantity_used == Decimal("2"))
    assert fee_disposal.proceeds_total_eur == Decimal("20")
