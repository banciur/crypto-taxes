from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from domain.inventory import OpenLotSnapshot
from domain.ledger import EventLocation, EventOrigin, EventType, LedgerEvent, LedgerLeg
from tests.helpers.test_price_service import TestPriceService
from utils.inventory_summary import compute_inventory_summary


def test_compute_inventory_summary_breaks_down_tax_free_holdings(price_service: TestPriceService) -> None:
    as_of = datetime(2025, 1, 10, tzinfo=timezone.utc)
    btc_tax_free_qty = Decimal("0.5")
    btc_recent_qty = Decimal("0.2")
    eth_qty = Decimal("1.2")
    eth_taxable_qty = Decimal("0")

    btc_rate = price_service.rate("BTC", "EUR", as_of)
    eth_rate = price_service.rate("ETH", "EUR", as_of)

    btc_total_qty = btc_tax_free_qty + btc_recent_qty
    btc_total_value = btc_total_qty * btc_rate
    btc_tax_free_value = btc_tax_free_qty * btc_rate
    btc_taxable_value = btc_recent_qty * btc_rate

    eth_taxable_value = eth_taxable_qty * eth_rate
    eth_total_value = eth_qty * eth_rate

    portfolio_total_value = btc_total_value + eth_total_value
    portfolio_tax_free_value = btc_tax_free_value + eth_total_value
    portfolio_taxable_value = portfolio_total_value - portfolio_tax_free_value

    open_inventory = [
        OpenLotSnapshot(
            lot_id=uuid4(),
            asset_id="BTC",
            acquired_timestamp=datetime(2023, 12, 1, tzinfo=timezone.utc),
            quantity_remaining=btc_tax_free_qty,
            cost_per_unit=Decimal("15000"),
        ),
        OpenLotSnapshot(
            lot_id=uuid4(),
            asset_id="BTC",
            acquired_timestamp=datetime(2024, 9, 1, tzinfo=timezone.utc),
            quantity_remaining=btc_recent_qty,
            cost_per_unit=Decimal("25000"),
        ),
        OpenLotSnapshot(
            lot_id=uuid4(),
            asset_id="ETH",
            acquired_timestamp=datetime(2023, 6, 15, tzinfo=timezone.utc),
            quantity_remaining=eth_qty,
            cost_per_unit=Decimal("1200"),
        ),
    ]

    summary = compute_inventory_summary(open_inventory, price_provider=price_service, as_of=as_of)
    assert summary.as_of == as_of
    assert summary.total_value_eur == portfolio_total_value
    assert summary.total_tax_free_value_eur == portfolio_tax_free_value
    assert summary.total_taxable_value_eur == portfolio_taxable_value

    assets = {asset.asset_id: asset for asset in summary.assets}

    btc = assets["BTC"]
    assert btc.total_quantity == btc_total_qty
    assert btc.tax_free_quantity == btc_tax_free_qty
    assert btc.taxable_quantity == btc_recent_qty
    assert btc.total_value_eur == btc_total_value
    assert btc.tax_free_value_eur == btc_tax_free_value
    assert btc.taxable_value_eur == btc_taxable_value
    assert btc.lots == 2

    eth = assets["ETH"]
    assert eth.total_quantity == eth_qty
    assert eth.tax_free_quantity == eth_qty
    assert eth.taxable_quantity == eth_taxable_qty
    assert eth.total_value_eur == eth_total_value
    assert eth.tax_free_value_eur == eth_total_value
    assert eth.taxable_value_eur == eth_taxable_value
    assert eth.lots == 1


def test_inventory_summary_filters_owned_wallets(price_service: TestPriceService) -> None:
    as_of = datetime(2025, 1, 10, tzinfo=timezone.utc)
    open_inventory = [
        OpenLotSnapshot(
            lot_id=uuid4(),
            asset_id="BTC",
            acquired_timestamp=datetime(2023, 12, 1, tzinfo=timezone.utc),
            quantity_remaining=Decimal("1.0"),
            cost_per_unit=Decimal("15000"),
        ),
        OpenLotSnapshot(
            lot_id=uuid4(),
            asset_id="ETH",
            acquired_timestamp=datetime(2024, 5, 1, tzinfo=timezone.utc),
            quantity_remaining=Decimal("2.0"),
            cost_per_unit=Decimal("1200"),
        ),
    ]

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

    summary = compute_inventory_summary(
        open_inventory, price_provider=price_service, as_of=as_of, owned_wallet_ids={"kraken"}, events=events
    )

    assert len(summary.assets) == 1
    asset = summary.assets[0]
    btc_rate = price_service.rate("BTC", "EUR", as_of)
    assert asset.asset_id == "BTC"
    assert asset.total_quantity == Decimal("1.0")
    assert asset.total_value_eur == Decimal("1.0") * btc_rate
