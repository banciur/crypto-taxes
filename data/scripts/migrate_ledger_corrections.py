from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from config import CORRECTIONS_DB_PATH, DB_PATH
from db.ledger_corrections_migration import migrate_legacy_corrections


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Migrate legacy spam/replacement corrections into ledger_corrections.")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--corrections-db", type=Path, default=CORRECTIONS_DB_PATH)
    args = parser.parse_args(argv)
    migrate_legacy_corrections(main_db_path=args.db, corrections_db_path=args.corrections_db)


if __name__ == "__main__":
    main()
