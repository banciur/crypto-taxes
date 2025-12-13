from __future__ import annotations

import csv
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from domain.ledger import AssetId, EventLocation, EventOrigin, EventType, LedgerEvent, LedgerLeg, WalletId

DEFAULT_SEED_TIMESTAMP = datetime(2000, 1, 1, tzinfo=timezone.utc)
DEFAULT_SEED_COST_TOTAL_EUR = Decimal("0.0001")


def load_seed_events(csv_path: Path) -> list[LedgerEvent]:
    """Load synthetic acquisition events seeded via CSV.

    Each row should contain: asset_id,wallet_id,quantity[,timestamp][,cost_total_eur][,note]
    Timestamps default to a distant past date (UTC) and cost defaults to 0.0001 EUR.
    """

    if not csv_path.exists():
        return []

    with csv_path.open() as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"Seed CSV {csv_path} is empty or missing headers")

        required = {"asset_id", "wallet_id", "quantity"}
        missing = required - set(reader.fieldnames)
        if missing:
            raise ValueError(f"Seed CSV {csv_path} missing required columns: {', '.join(sorted(missing))}")

        events: list[LedgerEvent] = []
        for row_idx, row in enumerate(reader, start=1):
            wallet_id = WalletId(row["wallet_id"].strip())
            asset_id = AssetId(row["asset_id"].strip())

            events.append(
                LedgerEvent(
                    timestamp=_parse_timestamp(row.get("timestamp") or row.get("acquired_timestamp")),
                    origin=EventOrigin(location=EventLocation.INTERNAL, external_id=f"seed_csv_row:{row_idx}"),
                    ingestion="seed_csv",
                    event_type=EventType.TRADE,
                    legs=[
                        LedgerLeg(asset_id=asset_id, quantity=Decimal(row["quantity"]), wallet_id=wallet_id),
                        LedgerLeg(
                            asset_id=AssetId("EUR"),
                            quantity=-_parse_cost(row.get("cost_total_eur")),
                            wallet_id=wallet_id,
                        ),
                    ],
                )
            )

    return events


def _parse_timestamp(raw: str | None) -> datetime:
    if not raw:
        return DEFAULT_SEED_TIMESTAMP
    ts = datetime.fromisoformat(raw)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _parse_cost(raw: str | None) -> Decimal:
    if raw is None or raw.strip() == "":
        return DEFAULT_SEED_COST_TOTAL_EUR
    cost = Decimal(raw)
    if cost <= 0:
        raise ValueError("Seed lot cost_total_eur must be positive")
    return cost
