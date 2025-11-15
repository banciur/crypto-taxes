from datetime import datetime, timedelta, timezone
from decimal import Decimal

from importers.kraken_importer import KrakenImporter, KrakenLedgerEntry


def _make_entry(
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


def test_preprocess_skips_spot_to_staking_pairs() -> None:
    importer = KrakenImporter("/tmp/dummy.csv")
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    entries = [
        _make_entry(
            refid="REF-A",
            txid="TX-A",
            subtype="spottostaking",
            asset="ETH",
            amount=Decimal("-4"),
            timestamp=ts,
        ),
        _make_entry(
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
        _make_entry(
            refid="REF-C",
            txid="TX-C",
            subtype="stakingtospot",
            asset="DOT.S",
            amount=Decimal("-100"),
            timestamp=ts,
        ),
        _make_entry(
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
