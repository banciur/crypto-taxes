from __future__ import annotations

import csv
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from domain.correction import SeedEvent
from domain.ledger import AccountId, AssetId, EventLocation, EventOrigin, LedgerEvent, LedgerLeg

DEFAULT_SEED_TIMESTAMP = datetime(2000, 1, 1, tzinfo=timezone.utc)
SEED_CSV_INGESTION = "seed_csv"


def load_seed_events(csv_path: Path) -> list[SeedEvent]:
    """Load seed lots (manual history) as correction events.

    Each row should contain: asset_id,account_id,quantity[,timestamp,price_per_token]
    Timestamp defaults to a distant past date (UTC).
    """

    if not csv_path.exists():
        return []

    with csv_path.open() as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"Seed CSV {csv_path} is empty or missing headers")

        has_account_id = "account_id" in reader.fieldnames
        has_legacy_wallet_id = "wallet_id" in reader.fieldnames
        if not has_account_id and not has_legacy_wallet_id:
            raise ValueError(f"Seed CSV {csv_path} missing required columns: account_id or wallet_id")
        required = {"asset_id", "quantity"}
        missing = required - set(reader.fieldnames)
        if missing:
            raise ValueError(f"Seed CSV {csv_path} missing required columns: {', '.join(sorted(missing))}")

        events: list[SeedEvent] = []
        for row in reader:
            raw_account_id = row.get("account_id") or row.get("wallet_id")
            if raw_account_id is None:
                raise ValueError("Seed CSV row is missing account_id")
            account_id = AccountId(raw_account_id.strip())
            asset_id = AssetId(row["asset_id"].strip())
            quantity = Decimal(row["quantity"].strip())
            if quantity <= 0:
                raise ValueError("Seed lot quantity must be positive")

            events.append(
                SeedEvent(
                    timestamp=_parse_timestamp(row.get("timestamp") or row.get("acquired_timestamp")),
                    price_per_token=_parse_price_per_token(row.get("price_per_token")),
                    legs=[
                        LedgerLeg(
                            asset_id=asset_id,
                            quantity=quantity,
                            account_id=account_id,
                        )
                    ],
                )
            )

    return events


def _parse_timestamp(raw: str | None) -> datetime:
    if raw is None:
        return DEFAULT_SEED_TIMESTAMP
    normalized = raw.strip()
    if not normalized:
        return DEFAULT_SEED_TIMESTAMP
    if normalized.endswith(("Z", "z")):
        normalized = f"{normalized[:-1]}+00:00"
    ts = datetime.fromisoformat(normalized)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _parse_price_per_token(raw: str | None) -> Decimal:
    if raw is None:
        return Decimal("0")
    normalized = raw.strip()
    if not normalized:
        return Decimal("0")
    value = Decimal(normalized)
    if value < 0:
        raise ValueError("Seed price_per_token must be >= 0")
    return value


def ledger_events_from_seed_events(seed_events: list[SeedEvent]) -> list[LedgerEvent]:
    events: list[LedgerEvent] = []
    for seed_event in seed_events:
        (leg,) = seed_event.legs
        events.append(
            LedgerEvent(
                timestamp=seed_event.timestamp,
                origin=EventOrigin(
                    location=EventLocation.INTERNAL,
                    external_id=f"seed:{seed_event.id}",
                ),
                ingestion=SEED_CSV_INGESTION,
                legs=[leg],
            )
        )
    return events
