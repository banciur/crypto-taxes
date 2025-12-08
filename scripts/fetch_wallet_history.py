# flake8: noqa: E402
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from clients.moralis import SyncMode, build_default_service
from importers.moralis import MoralisImporter


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch wallet history via Moralis and cache results.")
    parser.add_argument(
        "--accounts",
        type=Path,
        default=Path("data/accounts.json"),
        help="Path to accounts JSON (default: data/accounts.json)",
    )
    parser.add_argument(
        "--mode",
        type=SyncMode,
        choices=list(SyncMode),
        default=SyncMode.BUDGET,
        help="Sync mode: fresh hits API each time; budget uses cache when possible (default: budget).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("moralis_events.json"),
        help="Where to write emitted LedgerEvents as JSON (default: moralis_events.json)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    service = build_default_service(accounts_path=args.accounts)
    importer = MoralisImporter(service=service, mode=args.mode)
    events = importer.load_events()
    args.output.write_text(json.dumps([event.model_dump() for event in events], indent=2, default=str))
    print(f"Synced {len(events)} events (cached in DB) and wrote to {args.output}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    main()
