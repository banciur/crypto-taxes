from __future__ import annotations

from csv import DictWriter
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from itertools import count
from pathlib import Path

import pytest

from domain.ledger import EventLocation
from importers.kraken import KrakenImporter, KrakenLedgerEntry

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

DEFAULT_TS = datetime(2024, 1, 1, 12, 0)


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


def _preprocess_entry(
    *,
    refid: str,
    txid: str,
    subtype: str,
    asset: str,
    amount: Decimal,
    timestamp: datetime,
) -> KrakenLedgerEntry:
    return KrakenLedgerEntry(
        txid=txid,
        refid=refid,
        time=timestamp,
        type="transfer",
        subtype=subtype,
        aclass="currency",
        asset=asset,
        wallet="spot / main",
        amount=amount,
        fee=Decimal("0"),
        balance=Decimal("0"),
    )


def test_importer_sets_origin_and_ingestion(tmp_path: Path) -> None:
    refid = "REF-META-1"
    file = tmp_path / "origin.csv"
    write_csv(
        file,
        [
            ledger_row(
                refid=refid,
                ts=DEFAULT_TS,
                tx_type="deposit",
                asset="EUR",
                amount="10",
            )
        ],
    )

    event = KrakenImporter(str(file)).load_events()[0]

    assert event.origin.location == EventLocation.KRAKEN
    assert event.origin.external_id == refid
    assert event.ingestion == "kraken_ledger_csv"


def test_deposit_fiat_becomes_deposit_event(tmp_path: Path) -> None:
    amount = Decimal("100.5000")
    fee = Decimal("0.2500")
    file = tmp_path / "fiat_deposit.csv"
    write_csv(
        file,
        [
            ledger_row(
                ts=DEFAULT_TS,
                tx_type="deposit",
                asset="EUR",
                amount=str(amount),
                fee=str(fee),
                balance="100.5000",
            )
        ],
    )

    importer = KrakenImporter(str(file))
    events = importer.load_events()

    assert len(events) == 1
    event = events[0]
    assert event.timestamp == DEFAULT_TS.replace(tzinfo=timezone.utc)

    assert len(event.legs) == 2
    outside_leg = next(leg for leg in event.legs if leg.wallet_id == "outside")
    kraken_leg = next(leg for leg in event.legs if leg.wallet_id == "kraken")

    assert outside_leg.asset_id == "EUR"
    assert outside_leg.quantity == -amount
    assert kraken_leg.asset_id == "EUR"
    assert kraken_leg.quantity == amount - fee


def test_deposit_fiat_without_fee(tmp_path: Path) -> None:
    file = tmp_path / "fiat_deposit_no_fee.csv"
    write_csv(
        file,
        [
            ledger_row(
                ts=DEFAULT_TS,
                tx_type="deposit",
                asset="EUR",
                amount="500.0000",
            )
        ],
    )

    importer = KrakenImporter(str(file))
    event = importer.load_events()[0]

    assert len(event.legs) == 2
    outside_leg = next(leg for leg in event.legs if leg.wallet_id == "outside")
    kraken_leg = next(leg for leg in event.legs if leg.wallet_id == "kraken")
    assert outside_leg.quantity == Decimal("-500.0000")
    assert kraken_leg.quantity == Decimal("500.0000")


def test_deposit_crypto_becomes_transfer_event(tmp_path: Path) -> None:
    file = tmp_path / "crypto_deposit.csv"
    write_csv(
        file,
        [
            ledger_row(
                ts=DEFAULT_TS,
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
    assert event.timestamp == DEFAULT_TS.replace(tzinfo=timezone.utc)

    assert len(event.legs) == 2
    outside_leg = next(leg for leg in event.legs if leg.wallet_id == "outside")
    kraken_leg = next(leg for leg in event.legs if leg.wallet_id == "kraken")
    assert outside_leg.asset_id == "ETH"
    assert outside_leg.quantity == Decimal("-2.5")
    assert kraken_leg.asset_id == "ETH"
    assert kraken_leg.quantity == Decimal("2.5")


def test_deposit_crypto_with_fee(tmp_path: Path) -> None:
    amount = Decimal("0.25000000")
    fee = Decimal("0.00500000")
    file = tmp_path / "crypto_deposit_with_fee.csv"
    write_csv(
        file,
        [
            ledger_row(
                ts=DEFAULT_TS,
                tx_type="deposit",
                asset="BTC",
                amount=str(amount),
                fee=str(fee),
            )
        ],
    )

    importer = KrakenImporter(str(file))
    event = importer.load_events()[0]

    outside_leg = next(leg for leg in event.legs if leg.wallet_id == "outside")
    kraken_leg = next(leg for leg in event.legs if leg.wallet_id == "kraken")

    assert outside_leg.quantity == -amount
    assert kraken_leg.quantity == amount - fee


def test_withdrawal_fiat_becomes_withdrawal_event(tmp_path: Path) -> None:
    amount = Decimal("-250.0000")
    fee = Decimal("0.1000")
    file = tmp_path / "fiat_withdrawal.csv"
    write_csv(
        file,
        [
            ledger_row(
                ts=DEFAULT_TS,
                tx_type="withdrawal",
                asset="EUR",
                amount=str(amount),
                fee=str(fee),
            )
        ],
    )

    importer = KrakenImporter(str(file))
    events = importer.load_events()

    assert len(events) == 1
    event = events[0]
    assert event.timestamp == DEFAULT_TS.replace(tzinfo=timezone.utc)

    assert len(event.legs) == 2
    kraken_leg = next(leg for leg in event.legs if leg.wallet_id == "kraken")
    outside_leg = next(leg for leg in event.legs if leg.wallet_id == "outside")

    assert kraken_leg.asset_id == "EUR"
    assert kraken_leg.quantity == amount - fee
    assert outside_leg.quantity == abs(amount)


def test_withdrawal_fiat_without_fee(tmp_path: Path) -> None:
    file = tmp_path / "fiat_withdrawal_no_fee.csv"
    write_csv(
        file,
        [
            ledger_row(
                ts=DEFAULT_TS,
                tx_type="withdrawal",
                asset="EUR",
                amount="-400.0000",
            )
        ],
    )

    importer = KrakenImporter(str(file))
    event = importer.load_events()[0]

    kraken_leg = next(leg for leg in event.legs if leg.wallet_id == "kraken")
    outside_leg = next(leg for leg in event.legs if leg.wallet_id == "outside")

    assert kraken_leg.quantity == Decimal("-400.0000")
    assert outside_leg.quantity == Decimal("400.0000")


def test_withdrawal_crypto_becomes_transfer_event(tmp_path: Path) -> None:
    file = tmp_path / "crypto_withdrawal.csv"
    write_csv(
        file,
        [
            ledger_row(
                ts=DEFAULT_TS,
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
    assert event.timestamp == DEFAULT_TS.replace(tzinfo=timezone.utc)

    assert len(event.legs) == 2
    kraken_leg = next(leg for leg in event.legs if leg.wallet_id == "kraken")
    outside_leg = next(leg for leg in event.legs if leg.wallet_id == "outside")
    assert kraken_leg.asset_id == "ETH"
    assert kraken_leg.quantity == Decimal("-1.25")
    assert outside_leg.asset_id == "ETH"
    assert outside_leg.quantity == Decimal("1.25")


def test_withdrawal_crypto_with_fee(tmp_path: Path) -> None:
    amount = Decimal("-2.5000000000")
    fee = Decimal("0.0500000000")
    file = tmp_path / "crypto_withdrawal_with_fee.csv"
    write_csv(
        file,
        [
            ledger_row(
                ts=DEFAULT_TS,
                tx_type="withdrawal",
                asset="BTC",
                amount=str(amount),
                fee=str(fee),
            )
        ],
    )

    importer = KrakenImporter(str(file))
    event = importer.load_events()[0]

    assert event.timestamp == DEFAULT_TS.replace(tzinfo=timezone.utc)

    kraken_leg = next(leg for leg in event.legs if leg.wallet_id == "kraken")
    outside_leg = next(leg for leg in event.legs if leg.wallet_id == "outside")

    assert kraken_leg.asset_id == "BTC"
    assert kraken_leg.quantity == amount - fee
    assert outside_leg.asset_id == "BTC"
    assert outside_leg.quantity == abs(amount)


def test_trade_event_with_fee(tmp_path: Path) -> None:
    buy_amount = Decimal("1215.0000")
    buy_fee = Decimal("1.9440")
    file = tmp_path / "trade.csv"
    write_csv(
        file,
        [
            ledger_row(
                txid="T1",
                refid="R5",
                ts=DEFAULT_TS,
                tx_type="trade",
                subtype="tradespot",
                asset="ETH",
                amount="-0.4500000000",
            ),
            ledger_row(
                txid="T2",
                refid="R5",
                ts=DEFAULT_TS,
                tx_type="trade",
                subtype="tradespot",
                asset="EUR",
                amount=str(buy_amount),
                fee=str(buy_fee),
            ),
        ],
    )

    importer = KrakenImporter(str(file))
    events = importer.load_events()

    assert len(events) == 1
    event = events[0]
    assert event.timestamp == DEFAULT_TS.replace(tzinfo=timezone.utc)

    assert len(event.legs) == 2
    sell_leg = next(leg for leg in event.legs if leg.quantity < 0)
    buy_leg = next(leg for leg in event.legs if leg.quantity > 0)

    assert sell_leg.asset_id == "ETH"
    assert sell_leg.quantity == Decimal("-0.45")
    assert buy_leg.asset_id == "EUR"
    assert buy_leg.quantity == buy_amount - buy_fee


def test_spend_receive_trade(tmp_path: Path) -> None:
    amount_eur = Decimal("-172.2600")
    fee = Decimal("2.5900")
    file = tmp_path / "spend_receive_trade.csv"
    write_csv(
        file,
        [
            ledger_row(
                txid="SR1",
                refid="TSBW43U-4TCE7-ADKXQI",
                ts=DEFAULT_TS,
                tx_type="spend",
                asset="EUR",
                amount=str(amount_eur),
                fee=str(fee),
            ),
            ledger_row(
                txid="SR2",
                refid="TSBW43U-4TCE7-ADKXQI",
                ts=DEFAULT_TS,
                tx_type="receive",
                asset="DAI",
                amount="200.0000000000",
            ),
        ],
    )

    importer = KrakenImporter(str(file))
    event = importer.load_events()[0]

    assert event.timestamp == DEFAULT_TS.replace(tzinfo=timezone.utc)

    sell_leg = next(leg for leg in event.legs if leg.asset_id == "EUR")
    buy_leg = next(leg for leg in event.legs if leg.asset_id == "DAI")

    assert sell_leg.quantity == amount_eur - fee
    assert buy_leg.quantity == Decimal("200")


def test_staking_reward_with_fee(tmp_path: Path) -> None:
    amount = Decimal("0.0017569136")
    fee = Decimal("0.0003513827")
    file = tmp_path / "staking.csv"
    write_csv(
        file,
        [
            ledger_row(
                ts=DEFAULT_TS,
                tx_type="staking",
                asset="ETH",
                amount=str(amount),
                fee=str(fee),
            )
        ],
    )

    importer = KrakenImporter(str(file))
    events = importer.load_events()

    assert len(events) == 1
    event = events[0]
    assert event.timestamp == DEFAULT_TS.replace(tzinfo=timezone.utc)

    assert len(event.legs) == 1
    reward_leg = event.legs[0]

    assert reward_leg.asset_id == "ETH"
    assert reward_leg.quantity == amount - fee


def test_asset_aliases_are_applied(tmp_path: Path) -> None:
    file = tmp_path / "alias.csv"
    write_csv(
        file,
        [
            ledger_row(
                ts=DEFAULT_TS,
                tx_type="deposit",
                asset="DOT28.S",
                amount="10.0000",
            )
        ],
    )

    importer = KrakenImporter(str(file))
    event = importer.load_events()[0]

    assert event.legs[0].asset_id == "DOT"


def test_earn_reward_event(tmp_path: Path) -> None:
    file = tmp_path / "earn_reward.csv"
    write_csv(
        file,
        [
            ledger_row(
                ts=DEFAULT_TS,
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
    file = tmp_path / "spot_from_futures.csv"
    write_csv(
        file,
        [
            ledger_row(
                ts=DEFAULT_TS,
                tx_type="transfer",
                subtype="spotfromfutures",
                asset="STRK",
                amount="125.80924",
            )
        ],
    )

    importer = KrakenImporter(str(file))
    event = importer.load_events()[0]

    assert event.timestamp == DEFAULT_TS.replace(tzinfo=timezone.utc)
    assert len(event.legs) == 1
    assert event.legs[0].asset_id == "STRK"
    assert event.legs[0].quantity == Decimal("125.80924")


def test_spot_from_futures_event_with_fee_raises(tmp_path: Path) -> None:
    fee = Decimal("0.0025")
    file = tmp_path / "spot_from_futures_with_fee.csv"
    write_csv(
        file,
        [
            ledger_row(
                ts=DEFAULT_TS,
                tx_type="transfer",
                subtype="spotfromfutures",
                asset="STRK",
                amount="125.80924",
                fee=str(fee),
            )
        ],
    )

    importer = KrakenImporter(str(file))

    with pytest.raises(ValueError):
        importer.load_events()


def test_preprocess_skips_spot_to_staking_pairs() -> None:
    importer = KrakenImporter("/tmp/dummy.csv")
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    entries = [
        _preprocess_entry(
            refid="REF-A",
            txid="TX-A",
            subtype="spottostaking",
            asset="ETH",
            amount=Decimal("-4"),
            timestamp=ts,
        ),
        _preprocess_entry(
            refid="REF-B",
            txid="TX-B",
            subtype="stakingfromspot",
            asset="ETH2.S",
            amount=Decimal("4"),
            timestamp=ts + timedelta(hours=4),
        ),
    ]

    filtered = importer._preprocess_entries(entries)

    assert filtered == []


def test_preprocess_leaves_rows_outside_time_window() -> None:
    importer = KrakenImporter("/tmp/dummy.csv")
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    entries = [
        _preprocess_entry(
            refid="REF-C",
            txid="TX-C",
            subtype="stakingtospot",
            asset="DOT.S",
            amount=Decimal("-100"),
            timestamp=ts,
        ),
        _preprocess_entry(
            refid="REF-D",
            txid="TX-D",
            subtype="spotfromstaking",
            asset="DOT",
            amount=Decimal("100"),
            timestamp=ts + timedelta(days=6),
        ),
    ]

    filtered = importer._preprocess_entries(entries)

    assert len(filtered) == 2
    assert {entry.refid for entry in filtered} == {"REF-C", "REF-D"}
