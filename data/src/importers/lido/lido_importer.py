from __future__ import annotations

from csv import DictReader
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from accounts import account_chain_id_for
from domain.ledger import AssetId, EventLocation, EventOrigin, LedgerEvent, LedgerLeg, WalletAddress
from utils.misc import decimal_from_atomic_value, ensure_utc_datetime

LIDO_INGESTION_SOURCE = "lido_rewards_csv"
LIDO_EVENT_NOTE = "staking - Lido"
LIDO_ASSET_ID = AssetId("stETH")
LIDO_ASSET_DECIMALS = 18


@dataclass(frozen=True)
class _LidoRewardRow:
    timestamp: datetime
    quantity: Decimal
    external_id: str


def _parse_timestamp(raw_value: str) -> datetime:
    return ensure_utc_datetime(datetime.fromisoformat(raw_value.replace("Z", "+00:00")))


def _build_external_id(*, timestamp: datetime) -> str:
    return f"reward:{timestamp.isoformat()}"


class LidoImporter:
    def __init__(self, source_path: str | Path, *, wallet_address: str | WalletAddress) -> None:
        self._source_path = Path(source_path)
        self._account_chain_id = account_chain_id_for(
            location=EventLocation.ETHEREUM,
            address=WalletAddress(wallet_address),
        )

    def load_events(self) -> list[LedgerEvent]:
        events = [
            LedgerEvent(
                timestamp=row.timestamp,
                event_origin=EventOrigin(location=EventLocation.ETHEREUM, external_id=row.external_id),
                ingestion=LIDO_INGESTION_SOURCE,
                note=LIDO_EVENT_NOTE,
                legs=[
                    LedgerLeg(
                        asset_id=LIDO_ASSET_ID,
                        quantity=row.quantity,
                        account_chain_id=self._account_chain_id,
                    )
                ],
            )
            for row in self._read_rows()
        ]
        events.sort(key=lambda event: (event.timestamp, event.event_origin.external_id))
        return events

    def _read_rows(self) -> list[_LidoRewardRow]:
        rows: list[_LidoRewardRow] = []
        with self._source_path.open(encoding="utf-8-sig", newline="") as handle:
            reader = DictReader(handle)
            for raw_row in reader:
                if raw_row["type"] != "reward":
                    continue

                quantity = decimal_from_atomic_value(raw_row["change_wei"], LIDO_ASSET_DECIMALS)
                if quantity == 0:
                    continue
                timestamp = _parse_timestamp(raw_row["date"])

                rows.append(
                    _LidoRewardRow(
                        timestamp=timestamp,
                        quantity=quantity,
                        external_id=_build_external_id(timestamp=timestamp),
                    )
                )
        return rows
