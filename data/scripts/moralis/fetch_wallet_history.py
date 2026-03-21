# flake8: noqa: E402
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PROJECT_ROOT.parent
ARTIFACTS_DIR = REPO_ROOT / "artifacts"
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from accounts import AccountRegistry, load_accounts
from clients.moralis import MoralisClient
from config import CORRECTIONS_DB_PATH, TRANSACTIONS_CACHE_DB_PATH, config
from db.ledger_corrections import CorrectionsBase, LedgerCorrectionRepository
from db.session import init_db_session
from db.tx_cache_common import init_transactions_cache_db
from db.tx_cache_moralis import MoralisCacheRepository
from importers.moralis import MoralisImporter
from services.moralis import MoralisService, SyncMode


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch wallet history via Moralis and cache results.")
    parser.add_argument(
        "--accounts",
        type=Path,
        default=ARTIFACTS_DIR / "accounts.json",
        help="Path to accounts JSON (default: artifacts/accounts.json)",
    )
    parser.add_argument(
        "--sync_mode",
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

    accounts = load_accounts(args.accounts)
    cache_session = init_transactions_cache_db(db_path=TRANSACTIONS_CACHE_DB_PATH)
    corrections_session = init_db_session(
        db_path=CORRECTIONS_DB_PATH,
        metadata=CorrectionsBase.metadata,
        reset=False,
    )
    service = MoralisService(
        MoralisClient(api_key=config().moralis_api_key),
        MoralisCacheRepository(cache_session),
        accounts=accounts,
    )
    importer = MoralisImporter(
        service=service,
        account_registry=AccountRegistry(accounts),
        correction_repository=LedgerCorrectionRepository(corrections_session),
        sync_mode=args.sync_mode,
    )
    events = importer.load_events()
    args.output.write_text(json.dumps([event.model_dump() for event in events], indent=2, default=str))
    print(f"Synced {len(events)} events (cached in DB) and wrote to {args.output}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    main()
