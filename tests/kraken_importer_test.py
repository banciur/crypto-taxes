from __future__ import annotations

from csv import DictWriter
from datetime import datetime, timezone
from decimal import Decimal
from itertools import count
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


_txid_counter = count(1)
_refid_counter = count(1)


def ledger_row(
    *,
    txid: str | None = None,
    refid: str | None = None,
    ts: datetime,
    tx_type: str,
    asset: str,
    amount: str,
    subtype: str = "",
    aclass: str = "currency",
    wallet: str = "spot / main",
    fee: str = "0",
    balance: str = "0",
) -> dict[str, str]:
    if txid is None:
        txid = f"TX{next(_txid_counter)}"
    if refid is None:
        refid = f"REF{next(_refid_counter)}"
    return {
        "txid": txid,
        "refid": refid,
        "time": iso(ts),
        "type": tx_type,
        "subtype": subtype,
        "aclass": aclass,
        "asset": asset,
        "wallet": wallet,
        "amount": amount,
        "fee": fee,
        "balance": balance,
    }


def test_deposit_fiat_becomes_deposit_event(tmp_path: Path) -> None:
    ts = datetime(2024, 1, 1, 12, 0)
    file = tmp_path / "fiat_deposit.csv"
    write_csv(
        file,
        [
            ledger_row(
                ts=ts,
                tx_type="deposit",
                asset="EUR",
                amount="100.5000",
                fee="0.2500",
                balance="100.5000",
            )
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
    assert deposit_leg.wallet_id == "kraken"

    assert fee_leg.asset_id == "EUR"
    assert fee_leg.quantity == Decimal("-0.2500")


def test_deposit_crypto_becomes_transfer_event(tmp_path: Path) -> None:
    ts = datetime(2024, 2, 1, 9, 30)
    file = tmp_path / "crypto_deposit.csv"
    write_csv(
        file,
        [
            ledger_row(
                ts=ts,
                tx_type="deposit",
                asset="ETH",
                amount="2.5000000000",
                balance="2.5000000000",
            )
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
    assert leg.wallet_id == "kraken"


def test_withdrawal_fiat_becomes_withdrawal_event(tmp_path: Path) -> None:
    ts = datetime(2024, 3, 1, 15, 45)
    file = tmp_path / "fiat_withdrawal.csv"
    write_csv(
        file,
        [
            ledger_row(
                ts=ts,
                tx_type="withdrawal",
                asset="EUR",
                amount="-250.0000",
                fee="0.1000",
            )
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
            ledger_row(
                ts=ts,
                tx_type="withdrawal",
                asset="ETH",
                amount="-1.2500000000",
            )
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
            ledger_row(
                txid="T1",
                refid="R5",
                ts=ts,
                tx_type="trade",
                subtype="tradespot",
                asset="ETH",
                amount="-0.4500000000",
            ),
            ledger_row(
                txid="T2",
                refid="R5",
                ts=ts,
                tx_type="trade",
                subtype="tradespot",
                asset="EUR",
                amount="1215.0000",
                fee="1.9440",
            ),
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


def test_spend_receive_trade(tmp_path: Path) -> None:
    ts = datetime(2021, 11, 3, 22, 18, 32)
    file = tmp_path / "spend_receive_trade.csv"
    write_csv(
        file,
        [
            ledger_row(
                txid="SR1",
                refid="TSBW43U-4TCE7-ADKXQI",
                ts=ts,
                tx_type="spend",
                asset="EUR",
                amount="-172.2600",
                fee="2.5900",
            ),
            ledger_row(
                txid="SR2",
                refid="TSBW43U-4TCE7-ADKXQI",
                ts=ts,
                tx_type="receive",
                asset="DAI",
                amount="200.0000000000",
            ),
        ],
    )

    importer = KrakenImporter(str(file))
    event = importer.load_events()[0]

    assert event.event_type == EventType.TRADE
    assert event.timestamp == ts.replace(tzinfo=timezone.utc)

    sell_leg = next(leg for leg in event.legs if leg.asset_id == "EUR" and not leg.is_fee)
    buy_leg = next(leg for leg in event.legs if leg.asset_id == "DAI")
    fee_leg = next(leg for leg in event.legs if leg.is_fee)

    assert sell_leg.quantity == Decimal("-172.2600")
    assert buy_leg.quantity == Decimal("200")
    assert fee_leg.quantity == Decimal("-2.5900")


def test_staking_reward_with_fee(tmp_path: Path) -> None:
    ts = datetime(2024, 6, 2, 1, 46, 24)
    file = tmp_path / "staking.csv"
    write_csv(
        file,
        [
            ledger_row(
                ts=ts,
                tx_type="staking",
                asset="ETH",
                amount="0.0017569136",
                fee="0.0003513827",
            )
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
            ledger_row(
                ts=ts,
                tx_type="deposit",
                asset="DOT28.S",
                amount="10.0000",
            )
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
            ledger_row(
                ts=ts,
                tx_type="earn",
                subtype="reward",
                asset="USDC",
                amount="1.21127078",
                wallet="earn / flexible",
            )
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
            ledger_row(
                txid="SK1",
                refid="ELFI6E5-PNXZG-NSGNER",
                ts=ts1,
                tx_type="earn",
                subtype="allocation",
                asset="BTC",
                amount="-0.0000099500",
            ),
            ledger_row(
                txid="SK2",
                refid="ELFI6E5-PNXZG-NSGNER",
                ts=ts1,
                tx_type="earn",
                subtype="allocation",
                asset="BTC",
                amount="0.0000099500",
                wallet="earn / flexible",
            ),
            ledger_row(
                txid="SK3",
                refid="ELFI6E5-PNXZG-NSGNER",
                ts=ts2,
                tx_type="earn",
                subtype="deallocation",
                asset="BTC",
                amount="-0.0000099539",
                wallet="earn / flexible",
            ),
            ledger_row(
                txid="SK4",
                refid="ELFI6E5-PNXZG-NSGNER",
                ts=ts2,
                tx_type="earn",
                subtype="allocation",
                asset="BTC",
                amount="0.0000099539",
                wallet="earn / locked",
            ),
        ],
    )

    importer = KrakenImporter(str(file))
    events = importer.load_events()

    assert events == []


def test_spot_from_futures_event(tmp_path: Path) -> None:
    ts = datetime(2024, 2, 20, 12, 35, 53)
    file = tmp_path / "spot_from_futures.csv"
    write_csv(
        file,
        [
            ledger_row(
                ts=ts,
                tx_type="transfer",
                subtype="spotfromfutures",
                asset="STRK",
                amount="125.80924",
            )
        ],
    )

    importer = KrakenImporter(str(file))
    event = importer.load_events()[0]

    assert event.event_type == EventType.DROP
    assert event.timestamp == ts.replace(tzinfo=timezone.utc)
    assert len(event.legs) == 1
    assert event.legs[0].asset_id == "STRK"
    assert event.legs[0].quantity == Decimal("125.80924")
