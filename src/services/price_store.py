from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from .price_types import PriceQuote


class PriceStore(Protocol):
    def write(self, quote: PriceQuote) -> None: ...

    def read(self, base_id: str, quote_id: str, timestamp: datetime) -> PriceQuote | None: ...


class JsonlPriceStore(PriceStore):
    def __init__(self, *, root_dir: Path) -> None:
        self.root_dir = root_dir

    def write(self, quote: PriceQuote) -> None:
        path = self._file_path(quote.base_id, quote.quote_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": quote.timestamp.isoformat(),
            "base_id": quote.base_id,
            "quote_id": quote.quote_id,
            "rate": str(quote.rate),
            "source": quote.source,
            "valid_from": quote.valid_from.isoformat(),
            "valid_to": quote.valid_to.isoformat(),
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record))
            handle.write("\n")

    def read(self, base_id: str, quote_id: str, timestamp: datetime) -> PriceQuote | None:
        path = self._file_path(base_id, quote_id)
        if not path.exists():
            return None

        target_ts = timestamp
        best_record: dict[str, str] | None = None
        best_ts: datetime | None = None

        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                snapshot_ts = datetime.fromisoformat(record["timestamp"])
                valid_from = datetime.fromisoformat(record.get("valid_from", record["timestamp"]))
                valid_to_raw = record.get("valid_to")
                valid_to = datetime.fromisoformat(valid_to_raw) if valid_to_raw is not None else valid_from

                if not (valid_from <= target_ts <= valid_to):
                    continue

                if best_ts is None or snapshot_ts > best_ts:
                    best_record = record
                    best_ts = snapshot_ts

        if best_record is None or best_ts is None:
            return None

        return PriceQuote(
            timestamp=best_ts,
            base_id=best_record["base_id"],
            quote_id=best_record["quote_id"],
            rate=Decimal(best_record["rate"]),
            source=best_record["source"],
            valid_from=datetime.fromisoformat(best_record["valid_from"]),
            valid_to=datetime.fromisoformat(best_record["valid_to"]),
        )

    def _file_path(self, base_id: str, quote_id: str) -> Path:
        safe_base = base_id.upper()
        safe_quote = quote_id.upper()
        return self.root_dir / "prices" / f"{safe_base}-{safe_quote}.jsonl"


__all__ = ["JsonlPriceStore", "PriceStore"]
