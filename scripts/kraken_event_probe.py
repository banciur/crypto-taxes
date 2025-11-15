# flake8: noqa: E402
# uv run scripts/kraken_event_probe.py

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from collections import Counter

from domain.ledger import LedgerEvent
from importers.kraken_importer import KrakenImporter, KrakenLedgerEntry

UNKNOWN_PRINT_LIMIT = 150
# Set to a Kraken ledger row type (e.g., "deposit") to list all unresolved groups containing that type.
# Leave as None to display the latest UNKNOWN_PRINT_LIMIT unresolved groups regardless of type.
# UNRESOLVED_TYPE_FILTER: str | None = "withdrawal"
UNRESOLVED_TYPE_FILTER: str | None = None


@dataclass(slots=True)
class GroupResolution:
    refid: str
    entries: list[KrakenLedgerEntry]
    event: LedgerEvent | None
    error: Exception | None = None
    skipped_reason: str | None = None

    @property
    def resolved(self) -> bool:
        return self.error is None and self.event is not None

    @property
    def skipped(self) -> bool:
        return self.skipped_reason is not None


def resolve_group(importer: KrakenImporter, entries: Sequence[KrakenLedgerEntry]) -> LedgerEvent | None:
    """Invoke the real importer logic and return whatever it emits (including None)."""
    return importer._build_event(list(entries))  # type: ignore[attr-defined]


def iter_group_resolutions(
    importer: KrakenImporter,
    groups: dict[str, list[KrakenLedgerEntry]],
) -> Iterator[GroupResolution]:
    ordered_items = sorted(
        groups.items(),
        key=lambda pair: min(entry.time for entry in pair[1]),
    )
    for refid, entries in ordered_items:
        try:
            event = resolve_group(importer, entries)
        except Exception as exc:  # noqa: BLE001
            yield GroupResolution(refid=refid, entries=list(entries), event=None, error=exc)
            continue
        if event is None:
            yield GroupResolution(refid=refid, entries=list(entries), event=None, skipped_reason="returned_none")
        else:
            yield GroupResolution(refid=refid, entries=list(entries), event=event)


def _matches_filter(resolution: GroupResolution, entry_type: str) -> bool:
    return any(entry.type == entry_type for entry in resolution.entries)


def print_unknown_details(failures: list[GroupResolution]) -> None:
    if not failures:
        return

    if UNRESOLVED_TYPE_FILTER is not None:
        display = [res for res in failures if _matches_filter(res, UNRESOLVED_TYPE_FILTER)]
        print(
            f"\nUnresolved groups with entry type '{UNRESOLVED_TYPE_FILTER}': {len(display)} (out of {len(failures)})"
        )
    else:
        display = failures[:UNKNOWN_PRINT_LIMIT]
        print(f"\nMost recent {len(display)} unresolved groups (of {len(failures)} total):")

    for resolution in display:
        print(f"- refid={resolution.refid} :: {type(resolution.error).__name__}: {resolution.error}")
        for entry in resolution.entries:
            subtype = entry.subtype or ""
            print(
                f"    {entry.time.isoformat()} | type={entry.type:<10} subtype={subtype:<15} "
                f"asset={entry.asset:<10} wallet={entry.wallet:<20} amount={entry.amount} fee={entry.fee}"
            )
        print()


def summarize(path: Path) -> None:
    importer = KrakenImporter(str(path))
    entries = importer._read_entries()  # type: ignore[attr-defined]
    entries = importer._preprocess_entries(entries)  # type: ignore[attr-defined]
    groups = importer._group_by_refid(entries)  # type: ignore[attr-defined]

    total_groups = len(groups)
    total_rows = len(entries)

    resolved_events: list[LedgerEvent] = []
    failures: list[GroupResolution] = []
    skipped: list[GroupResolution] = []

    for resolution in iter_group_resolutions(importer, groups):
        if resolution.resolved and resolution.event is not None:
            resolved_events.append(resolution.event)
        elif resolution.skipped:
            skipped.append(resolution)
        else:
            failures.append(resolution)

    print(f"Ledger rows: {total_rows}")
    print(f"Refid groups: {total_groups}")
    print(f"Resolved events: {len(resolved_events)}")
    print(f"Unresolved groups: {len(failures)}")
    print(f"Skipped groups: {len(skipped)}")

    if skipped:
        reason_counts = Counter(res.skipped_reason or "unknown" for res in skipped)
        print("Skip reasons:")
        for reason, count in sorted(reason_counts.items()):
            print(f"  {reason:<20} {count}")

    print_unknown_details(failures)


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Iterate Kraken ledger entries, emit events via the importer, and report unresolved groups.",
    )
    parser.add_argument(
        "path",
        type=Path,
        nargs="?",
        default=Path("data/kraken-ledger.csv"),
        help="Path to Kraken ledger CSV (default: data/kraken-ledger.csv)",
    )
    args = parser.parse_args(argv)
    summarize(args.path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler()])
    main()
