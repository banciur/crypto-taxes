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


def test_trade_event_with_fee(tmp_path: Path) -> None:
    ts = datetime(2024, 5, 1, 12, 0)
    file = tmp_path / "trade.csv"
    write_csv(
        file,
        [
            {
                "txid": "T1",
                "refid": "R5",
                "time": iso(ts),
                "type": "trade",
                "subtype": "tradespot",
                "aclass": "currency",
                "asset": "ETH",
                "wallet": "spot / main",
                "amount": "-0.4500000000",
                "fee": "0",
                "balance": "0",
            },
            {
                "txid": "T2",
                "refid": "R5",
                "time": iso(ts),
                "type": "trade",
                "subtype": "tradespot",
                "aclass": "currency",
                "asset": "EUR",
                "wallet": "spot / main",
                "amount": "1215.0000",
                "fee": "1.9440",
                "balance": "0",
            },
        ],
    )

    importer = KrakenImporter(str(file))
    events = importer.load_events()

    assert len(events) == 1
    event = events[0]
    assert event.event_type == EventType.TRADE
    assert event.timestamp == ts.replace(tzinfo=timezone.utc)

    non_fee = [leg for leg in event.legs if not leg.is_fee]
    fee_legs = [leg for leg in event.legs if leg.is_fee]

    assert len(non_fee) == 2
    sell_leg = next(leg for leg in non_fee if leg.quantity < 0)
    buy_leg = next(leg for leg in non_fee if leg.quantity > 0)

    assert sell_leg.asset_id == "ETH"
    assert sell_leg.quantity == Decimal("-0.45")
    assert buy_leg.asset_id == "EUR"
    assert buy_leg.quantity == Decimal("1215")

    assert len(fee_legs) == 1
    assert fee_legs[0].asset_id == "EUR"
    assert fee_legs[0].quantity == Decimal("-1.9440")


def test_staking_reward_with_fee(tmp_path: Path) -> None:
    ts = datetime(2024, 6, 2, 1, 46, 24)
    file = tmp_path / "staking.csv"
    write_csv(
        file,
        [
            {
                "txid": "S1",
                "refid": "R6",
                "time": iso(ts),
                "type": "staking",
                "subtype": "",
                "aclass": "currency",
                "asset": "ETH",
                "wallet": "spot / main",
                "amount": "0.0017569136",
                "fee": "0.0003513827",
                "balance": "0",
            }
        ],
    )

    importer = KrakenImporter(str(file))
    events = importer.load_events()

    assert len(events) == 1
    event = events[0]
    assert event.event_type == EventType.REWARD
    assert event.timestamp == ts.replace(tzinfo=timezone.utc)

    reward_leg = next(leg for leg in event.legs if not leg.is_fee)
    fee_leg = next(leg for leg in event.legs if leg.is_fee)

    assert reward_leg.asset_id == "ETH"
    assert reward_leg.quantity == Decimal("0.0017569136")
    assert fee_leg.quantity == Decimal("-0.0003513827")


def test_asset_aliases_are_applied(tmp_path: Path) -> None:
    ts = datetime(2024, 7, 1, 12, 0)
    file = tmp_path / "alias.csv"
    write_csv(
        file,
        [
            {
                "txid": "A1",
                "refid": "R7",
                "time": iso(ts),
                "type": "deposit",
                "subtype": "",
                "aclass": "currency",
                "asset": "DOT28.S",
                "wallet": "spot / main",
                "amount": "10.0000",
                "fee": "0",
                "balance": "0",
            }
        ],
    )

    importer = KrakenImporter(str(file))
    event = importer.load_events()[0]

    assert event.event_type == EventType.TRANSFER  # DOT is not fiat
    assert event.legs[0].asset_id == "DOT"


def test_earn_reward_event(tmp_path: Path) -> None:
    ts = datetime(2024, 3, 1, 6, 43, 18)
    file = tmp_path / "earn_reward.csv"
    write_csv(
        file,
        [
            {
                "txid": "E1",
                "refid": "R8",
                "time": iso(ts),
                "type": "earn",
                "subtype": "reward",
                "aclass": "currency",
                "asset": "USDC",
                "wallet": "earn / flexible",
                "amount": "1.21127078",
                "fee": "0",
                "balance": "0",
            }
        ],
    )

    importer = KrakenImporter(str(file))
    event = importer.load_events()[0]

    assert event.event_type == EventType.REWARD
    assert event.legs[0].asset_id == "USDC"
    assert event.legs[0].quantity == Decimal("1.21127078")


def test_explicit_refid_skip(tmp_path: Path) -> None:
    ts1 = datetime(2024, 4, 17, 20, 36, 43)
    ts2 = datetime(2024, 9, 10, 13, 48, 39)
    file = tmp_path / "skip_refid.csv"
    write_csv(
        file,
        [
            {
                "txid": "SK1",
                "refid": "ELFI6E5-PNXZG-NSGNER",
                "time": iso(ts1),
                "type": "earn",
                "subtype": "allocation",
                "aclass": "currency",
                "asset": "BTC",
                "wallet": "spot / main",
                "amount": "-0.0000099500",
                "fee": "0",
                "balance": "0",
            },
            {
                "txid": "SK2",
                "refid": "ELFI6E5-PNXZG-NSGNER",
                "time": iso(ts1),
                "type": "earn",
                "subtype": "allocation",
                "aclass": "currency",
                "asset": "BTC",
                "wallet": "earn / flexible",
                "amount": "0.0000099500",
                "fee": "0",
                "balance": "0",
            },
            {
                "txid": "SK3",
                "refid": "ELFI6E5-PNXZG-NSGNER",
                "time": iso(ts2),
                "type": "earn",
                "subtype": "deallocation",
                "aclass": "currency",
                "asset": "BTC",
                "wallet": "earn / flexible",
                "amount": "-0.0000099539",
                "fee": "0",
                "balance": "0",
            },
            {
                "txid": "SK4",
                "refid": "ELFI6E5-PNXZG-NSGNER",
                "time": iso(ts2),
                "type": "earn",
                "subtype": "allocation",
                "aclass": "currency",
                "asset": "BTC",
                "wallet": "earn / locked",
                "amount": "0.0000099539",
                "fee": "0",
                "balance": "0",
            },
        ],
    )

    importer = KrakenImporter(str(file))
    events = importer.load_events()

    assert events == []
