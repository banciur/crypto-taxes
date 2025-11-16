# flake8: noqa: E402
# uv run scripts/kraken_row_range_import.py 10 25 --csv data/kraken-ledger.csv
from __future__ import annotations

import argparse
import sys
from csv import DictReader
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from domain.ledger import LedgerEvent  # noqa: E402
from importers.kraken_importer import KrakenImporter, KrakenLedgerEntry  # noqa: E402


def _load_rows(csv_path: Path, start_row: int, end_row: int) -> list[tuple[int, KrakenLedgerEntry]]:
    selected: list[tuple[int, KrakenLedgerEntry]] = []
    with csv_path.open(encoding="utf-8") as handle:
        reader = DictReader(handle)
        for row_number, row in enumerate(reader, start=1):
            if row_number < start_row:
                continue
            if row_number > end_row:
                break
            selected.append((row_number, KrakenLedgerEntry.model_validate(row)))
    return selected


def _format_event(event: LedgerEvent, refid: str, row_numbers: list[int]) -> str:
    rows = ", ".join(str(number) for number in row_numbers) or "n/a"
    header = [
        f"refid={refid}",
        f"rows={rows}",
        f"type={event.event_type}",
        f"timestamp={event.timestamp.isoformat()}",
    ]
    lines = [" | ".join(header)]
    for leg in event.legs:
        fee_marker = " (fee)" if leg.is_fee else ""
        lines.append(
            f"    asset={leg.asset_id:<8} qty={leg.quantity} wallet={leg.wallet_id}{fee_marker}",
        )
    return "\n".join(lines)


def run(csv_path: Path, start_row: int, end_row: int) -> None:
    if start_row < 1:
        raise ValueError("start_row must be >= 1")
    if end_row < start_row:
        raise ValueError("end_row must be >= start_row")

    rows = _load_rows(csv_path, start_row, end_row)
    if not rows:
        print(f"No ledger rows found in range {start_row}-{end_row}.")
        return

    importer = KrakenImporter(str(csv_path))

    entries = [entry for _, entry in rows]
    row_numbers_by_txid = {entry.txid: row_number for row_number, entry in rows}
    preprocessed = importer._preprocess_entries(entries)  # type: ignore[attr-defined]
    if not preprocessed:
        print("Selected rows did not yield any entries after preprocessing.")
        return

    groups = importer._group_by_refid(preprocessed)  # type: ignore[attr-defined]
    ordered = sorted(groups.items(), key=lambda pair: min(entry.time for entry in pair[1]))

    produced_events = 0
    skipped_groups = 0
    failed_groups = 0

    print(
        f"Processing rows {start_row}-{end_row} ({len(rows)} source rows, "
        f"{len(preprocessed)} entries after preprocessing)",
    )

    for refid, group_entries in ordered:
        group_row_numbers = sorted(
            row_number for entry in group_entries if (row_number := row_numbers_by_txid.get(entry.txid)) is not None
        )
        try:
            event = importer._build_event(group_entries)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            failed_groups += 1
            print(f"[refid={refid}] ERROR: {type(exc).__name__}: {exc}")
            continue
        if event is None:
            skipped_groups += 1
            print(f"[refid={refid}] Skipped (importer returned None).")
            continue
        produced_events += 1
        print()
        print(_format_event(event, refid, [number for number in group_row_numbers if number is not None]))

    print()
    print(
        f"Completed. Events: {produced_events}, skipped groups: {skipped_groups}, errors: {failed_groups}",
    )


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Feed a row range from the Kraken ledger CSV into the importer and display the resulting events. "
            "Row numbers are 1-based and count data rows (header excluded)."
        ),
    )
    parser.add_argument("start_row", type=int, help="First CSV row to include (1-based).")
    parser.add_argument("end_row", type=int, help="Last CSV row to include (1-based, inclusive).")
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("data/kraken-ledger.csv"),
        help="Path to the Kraken ledger CSV (default: data/kraken-ledger.csv).",
    )
    args = parser.parse_args(argv)
    run(args.csv, args.start_row, args.end_row)


if __name__ == "__main__":
    main()
