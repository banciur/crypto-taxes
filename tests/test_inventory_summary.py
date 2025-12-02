from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from domain.ledger import EventLocation, EventOrigin, EventType, LedgerEvent, LedgerLeg
from tests.helpers.test_price_service import TestPriceService
from utils.inventory_summary import compute_inventory_summary


def test_compute_inventory_summary_calculates_totals(price_service: TestPriceService) -> None:
    as_of = datetime(2025, 1, 10, tzinfo=timezone.utc)
    btc_lot_one_qty = Decimal("0.5")
    btc_lot_two_qty = Decimal("0.2")
    eth_qty = Decimal("1.2")

    btc_rate = price_service.rate("BTC", "EUR", as_of)
    eth_rate = price_service.rate("ETH", "EUR", as_of)

    btc_total_qty = btc_lot_one_qty + btc_lot_two_qty
    btc_total_value = btc_total_qty * btc_rate
    eth_total_value = eth_qty * eth_rate

    events = [
        LedgerEvent(
            timestamp=datetime(2023, 12, 1, tzinfo=timezone.utc),
            origin=EventOrigin(location=EventLocation.INTERNAL, external_id=f"evt-{uuid4()}"),
            ingestion="test",
            event_type=EventType.DEPOSIT,
            legs=[
                LedgerLeg(asset_id="BTC", quantity=btc_lot_one_qty, wallet_id="kraken"),
                LedgerLeg(asset_id="EUR", quantity=Decimal("-1.0"), wallet_id="kraken"),
            ],
        ),
        LedgerEvent(
            timestamp=datetime(2024, 9, 1, tzinfo=timezone.utc),
            origin=EventOrigin(location=EventLocation.INTERNAL, external_id=f"evt-{uuid4()}"),
            ingestion="test",
            event_type=EventType.DEPOSIT,
            legs=[
                LedgerLeg(asset_id="BTC", quantity=btc_lot_two_qty, wallet_id="kraken"),
                LedgerLeg(asset_id="EUR", quantity=Decimal("-1.0"), wallet_id="kraken"),
            ],
        ),
        LedgerEvent(
            timestamp=datetime(2023, 6, 15, tzinfo=timezone.utc),
            origin=EventOrigin(location=EventLocation.INTERNAL, external_id=f"evt-{uuid4()}"),
            ingestion="test",
            event_type=EventType.DEPOSIT,
            legs=[
                LedgerLeg(asset_id="ETH", quantity=eth_qty, wallet_id="kraken"),
                LedgerLeg(asset_id="EUR", quantity=Decimal("-1.0"), wallet_id="kraken"),
            ],
        ),
    ]

    summary = compute_inventory_summary(events, {"kraken"}, price_provider=price_service, as_of=as_of)
    assert summary.as_of == as_of

    assets = {asset.asset_id: asset for asset in summary.assets}

    btc = assets["BTC"]
    assert btc.total_quantity == btc_total_qty
    assert btc.total_value_eur == btc_total_value

    eth = assets["ETH"]
    assert eth.total_quantity == eth_qty
    assert eth.total_value_eur == eth_total_value


def test_inventory_summary_filters_owned_wallets(price_service: TestPriceService) -> None:
    as_of = datetime(2025, 1, 10, tzinfo=timezone.utc)
    events = [
        LedgerEvent(
            timestamp=datetime(2023, 12, 1, tzinfo=timezone.utc),
            origin=EventOrigin(location=EventLocation.INTERNAL, external_id="evt-1"),
            ingestion="test",
            event_type=EventType.DEPOSIT,
            legs=[
                LedgerLeg(asset_id="BTC", quantity=Decimal("1.0"), wallet_id="kraken"),
                LedgerLeg(asset_id="EUR", quantity=Decimal("-1.0"), wallet_id="kraken"),
            ],
        ),
        LedgerEvent(
            timestamp=datetime(2024, 5, 1, tzinfo=timezone.utc),
            origin=EventOrigin(location=EventLocation.INTERNAL, external_id="evt-2"),
            ingestion="test",
            event_type=EventType.DEPOSIT,
            legs=[
                LedgerLeg(asset_id="ETH", quantity=Decimal("2.0"), wallet_id="outside"),
                LedgerLeg(asset_id="EUR", quantity=Decimal("-1.0"), wallet_id="outside"),
            ],
        ),
    ]

    summary = compute_inventory_summary(events, owned_wallet_ids={"kraken"}, price_provider=price_service, as_of=as_of)

    assert len(summary.assets) == 1
    asset = summary.assets[0]
    btc_rate = price_service.rate("BTC", "EUR", as_of)
    assert asset.asset_id == "BTC"
    assert asset.total_quantity == Decimal("1.0")
    assert asset.total_value_eur == Decimal("1.0") * btc_rate
