# This file is completely vibed and I didn't read it.
from __future__ import annotations

from csv import DictReader
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from accounts import account_chain_id_for
from domain.ledger import AssetId, EventLocation, EventOrigin, LedgerEvent, LedgerLeg, WalletAddress

STAKEWISE_INGESTION_SOURCE = "stakewise_rewards_csv"


@dataclass(frozen=True)
class _StakewiseRewardRow:
    timestamp: datetime
    asset_id: AssetId
    quantity: Decimal
    external_id: str


@dataclass(frozen=True)
class _StakewiseSourceBatch:
    path: Path
    rows: tuple[_StakewiseRewardRow, ...]
    span_days: int


def _extract_reward_column(fieldnames: list[str]) -> str:
    reward_columns = [name for name in fieldnames if name.startswith("Reward (") and name != "Reward (USD)"]
    if len(reward_columns) != 1:
        raise ValueError(f"Stakewise CSV must contain exactly one non-USD reward column, got {reward_columns}")
    return reward_columns[0]


def _extract_date_column(fieldnames: list[str]) -> str:
    date_columns = [name for name in fieldnames if name.startswith("Date (")]
    if len(date_columns) != 1:
        raise ValueError(f"Stakewise CSV must contain exactly one date column, got {date_columns}")
    return date_columns[0]


def _parse_asset_id(column_name: str) -> AssetId:
    prefix = "Reward ("
    if not column_name.startswith(prefix) or not column_name.endswith(")"):
        raise ValueError(f"Unsupported Stakewise reward column {column_name}")
    return AssetId(column_name[len(prefix) : -1])


def _parse_timestamp(raw_value: str, *, date_column: str) -> datetime:
    if date_column == "Date (MM/DD/YYYY)":
        parsed = datetime.strptime(raw_value, "%m/%d/%Y")
        return parsed.replace(tzinfo=UTC)
    if date_column == "Date (YYYY-MM-DD)":
        return datetime.strptime(raw_value, "%Y-%m-%d %H:%M UTC").replace(tzinfo=UTC)
    raise ValueError(f"Unsupported Stakewise date column {date_column}")


def _build_external_id(*, timestamp: datetime, asset_id: AssetId) -> str:
    return f"reward:{timestamp.date().isoformat()}:{asset_id}"


class StakewiseImporter:
    def __init__(self, source_paths: Iterable[str | Path], *, wallet_address: str | WalletAddress) -> None:
        self._source_paths = tuple(Path(path) for path in source_paths)
        self._account_chain_id = account_chain_id_for(
            location=EventLocation.ETHEREUM,
            address=WalletAddress(wallet_address),
        )

    def load_events(self) -> list[LedgerEvent]:
        merged_rows: dict[str, _StakewiseRewardRow] = {}
        for batch in sorted(self._read_batches(), key=lambda item: (item.span_days, len(item.rows), item.path.name)):
            for row in batch.rows:
                merged_rows[row.external_id] = row

        events = [
            LedgerEvent(
                timestamp=row.timestamp,
                event_origin=EventOrigin(location=EventLocation.ETHEREUM, external_id=row.external_id),
                ingestion=STAKEWISE_INGESTION_SOURCE,
                legs=[
                    LedgerLeg(
                        asset_id=row.asset_id,
                        quantity=row.quantity,
                        account_chain_id=self._account_chain_id,
                    )
                ],
            )
            for row in merged_rows.values()
            if row.quantity != 0
        ]
        events.sort(key=lambda event: (event.timestamp, event.event_origin.external_id))
        return events

    def _read_batches(self) -> list[_StakewiseSourceBatch]:
        return [self._read_batch(path) for path in self._source_paths]

    def _read_batch(self, path: Path) -> _StakewiseSourceBatch:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = DictReader(handle)
            fieldnames = list(reader.fieldnames or [])
            reward_column = _extract_reward_column(fieldnames)
            date_column = _extract_date_column(fieldnames)
            asset_id = _parse_asset_id(reward_column)

            parsed_rows: list[_StakewiseRewardRow] = []
            for raw_row in reader:
                timestamp = _parse_timestamp(raw_row[date_column], date_column=date_column)
                parsed_rows.append(
                    _StakewiseRewardRow(
                        timestamp=timestamp,
                        asset_id=asset_id,
                        quantity=Decimal(raw_row[reward_column]),
                        external_id=_build_external_id(timestamp=timestamp, asset_id=asset_id),
                    )
                )
            rows = tuple(parsed_rows)

        if not rows:
            return _StakewiseSourceBatch(path=path, rows=rows, span_days=0)

        timestamps = [row.timestamp for row in rows]
        span_days = (max(timestamps).date() - min(timestamps).date()).days + 1
        return _StakewiseSourceBatch(path=path, rows=rows, span_days=span_days)
