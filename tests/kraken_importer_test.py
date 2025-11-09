from __future__ import annotations

from csv import DictWriter
from datetime import datetime
from pathlib import Path

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
        for row in rows:
            writer.writerow(row)


def iso(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%d %H:%M:%S")


def test_importer_raises_until_event_builder_exists(tmp_path: Path) -> None:
    file = tmp_path / "unimplemented.csv"
    write_csv(
        file,
        [
            {
                "txid": "T1",
                "refid": "R1",
                "time": iso(datetime(2024, 1, 1, 12, 0)),
                "type": "trade",
                "subtype": "tradespot",
                "aclass": "currency",
                "asset": "ETH",
                "wallet": "spot / main",
                "amount": "-1.0000000000",
                "fee": "0",
                "balance": "0",
            },
        ],
    )

    importer = KrakenImporter(str(file))

    try:
        importer.load_events()
    except ValueError as exc:
        assert "not implemented" in str(exc)
    else:  # pragma: no cover - defensive until implementation exists
        raise AssertionError("Importer should raise until event builder is implemented")
