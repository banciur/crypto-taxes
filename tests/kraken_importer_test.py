from __future__ import annotations

from csv import DictWriter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from domain.ledger import EventType
from importers.kraken_importer import KrakenImporter

FIELDNAMES = [
    "txid",
    "refid",
    "time",
    "type",
    "subtype",
    "aclass",
    "asset",
    "wallet",
    "amount",
    "fee",
    "balance",
]


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def iso(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%d %H:%M:%S")


def test_deposit_fiat_becomes_deposit_event(tmp_path: Path) -> None:
    ts = datetime(2024, 1, 1, 12, 0)
    file = tmp_path / "fiat_deposit.csv"
    write_csv(
        file,
        [
            {
                "txid": "D1",
                "refid": "R1",
                "time": iso(ts),
                "type": "deposit",
                "subtype": "",
                "aclass": "currency",
                "asset": "EUR",
                "wallet": "spot / main",
                "amount": "100.5000",
                "fee": "0.2500",
                "balance": "100.5000",
            }
        ],
    )

    importer = KrakenImporter(str(file))
    events = importer.load_events()

    assert len(events) == 1
    event = events[0]
    assert event.event_type == EventType.DEPOSIT
    assert event.timestamp == ts.replace(tzinfo=timezone.utc)

    legs = event.legs
    assert len(legs) == 2  # deposit leg + fee leg
    deposit_leg = next(leg for leg in legs if not leg.is_fee)
    fee_leg = next(leg for leg in legs if leg.is_fee)

    assert deposit_leg.asset_id == "EUR"
    assert deposit_leg.quantity == Decimal("100.5000")
    assert deposit_leg.wallet_id == "kraken::spot / main"

    assert fee_leg.asset_id == "EUR"
    assert fee_leg.quantity == Decimal("-0.2500")


def test_deposit_crypto_becomes_transfer_event(tmp_path: Path) -> None:
    ts = datetime(2024, 2, 1, 9, 30)
    file = tmp_path / "crypto_deposit.csv"
    write_csv(
        file,
        [
            {
                "txid": "C1",
                "refid": "R2",
                "time": iso(ts),
                "type": "deposit",
                "subtype": "",
                "aclass": "currency",
                "asset": "ETH",
                "wallet": "spot / main",
                "amount": "2.5000000000",
                "fee": "0",
                "balance": "2.5000000000",
            }
        ],
    )

    importer = KrakenImporter(str(file))
    events = importer.load_events()

    assert len(events) == 1
    event = events[0]
    assert event.event_type == EventType.TRANSFER
    assert event.timestamp == ts.replace(tzinfo=timezone.utc)

    assert len(event.legs) == 1
    leg = event.legs[0]
    assert leg.asset_id == "ETH"
    assert leg.quantity == Decimal("2.5")
    assert leg.wallet_id == "kraken::spot / main"


def test_withdrawal_fiat_becomes_withdrawal_event(tmp_path: Path) -> None:
    ts = datetime(2024, 3, 1, 15, 45)
    file = tmp_path / "fiat_withdrawal.csv"
    write_csv(
        file,
        [
            {
                "txid": "W1",
                "refid": "R3",
                "time": iso(ts),
                "type": "withdrawal",
                "subtype": "",
                "aclass": "currency",
                "asset": "EUR",
                "wallet": "spot / main",
                "amount": "-250.0000",
                "fee": "0.1000",
                "balance": "0",
            }
        ],
    )

    importer = KrakenImporter(str(file))
    events = importer.load_events()

    assert len(events) == 1
    event = events[0]
    assert event.event_type == EventType.WITHDRAWAL
    assert event.timestamp == ts.replace(tzinfo=timezone.utc)

    assert len(event.legs) == 2
    main_leg = next(leg for leg in event.legs if not leg.is_fee)
    fee_leg = next(leg for leg in event.legs if leg.is_fee)

    assert main_leg.asset_id == "EUR"
    assert main_leg.quantity == Decimal("-250.0000")
    assert fee_leg.quantity == Decimal("-0.1000")


def test_withdrawal_crypto_becomes_transfer_event(tmp_path: Path) -> None:
    ts = datetime(2024, 4, 1, 10, 0)
    file = tmp_path / "crypto_withdrawal.csv"
    write_csv(
        file,
        [
            {
                "txid": "W2",
                "refid": "R4",
                "time": iso(ts),
                "type": "withdrawal",
                "subtype": "",
                "aclass": "currency",
                "asset": "ETH",
                "wallet": "spot / main",
                "amount": "-1.2500000000",
                "fee": "0",
                "balance": "0",
            }
        ],
    )

    importer = KrakenImporter(str(file))
    events = importer.load_events()

    assert len(events) == 1
    event = events[0]
    assert event.event_type == EventType.TRANSFER
    assert event.timestamp == ts.replace(tzinfo=timezone.utc)

    assert len(event.legs) == 1
    leg = event.legs[0]
    assert leg.asset_id == "ETH"
    assert leg.quantity == Decimal("-1.25")
