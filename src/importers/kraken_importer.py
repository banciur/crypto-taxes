from __future__ import annotations

from collections import defaultdict
from csv import DictReader
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel, Field, field_validator

from domain.ledger import EventType, LedgerEvent, LedgerLeg

FIAT_ASSETS = {"EUR", "USD"}


class KrakenLedgerEntry(BaseModel):
    txid: str
    refid: str
    time: datetime
    type: str
    subtype: str | None = None
    aclass: str
    asset: str
    wallet: str
    amount: Decimal = Field(alias="amount")
    fee: Decimal
    balance: Decimal

    @field_validator("time", mode="before")
    @classmethod
    def _parse_timestamp(cls, value: str | datetime) -> datetime:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)

    @field_validator("subtype", mode="before")
    @classmethod
    def _empty_subtype(cls, value: str | None) -> str | None:
        if value == "":
            return None
        return value

    @field_validator("amount", "fee", "balance", mode="before")
    @classmethod
    def _ensure_decimal(cls, value: str | Decimal) -> str | Decimal:
        if value == "":
            return "0"
        return value


def _wallet_id(wallet_name: str) -> str:
    return f"kraken::{wallet_name.strip()}"


def _ledger_leg(entry: KrakenLedgerEntry, quantity: Decimal, *, is_fee: bool = False) -> LedgerLeg:
    return LedgerLeg(
        asset_id=entry.asset,
        quantity=quantity,
        wallet_id=_wallet_id(entry.wallet),
        is_fee=is_fee,
    )


def _fee_legs(entry: KrakenLedgerEntry) -> list[LedgerLeg]:
    if entry.fee == 0:
        return []
    return [_ledger_leg(entry, entry.fee * Decimal("-1"), is_fee=True)]


class KrakenImporter:
    def __init__(self, source_path: str) -> None:
        self._source_path = Path(source_path)

    def load_events(self) -> list[LedgerEvent]:
        entries = self._read_entries()
        events: list[LedgerEvent] = []
        for group in self._group_by_refid(entries).values():
            event = self._build_event(group)
            if event is not None:
                events.append(event)
        events.sort(key=lambda evt: evt.timestamp)
        return events

    def perform_import(self) -> list[LedgerEvent]:
        return self.load_events()

    def _read_entries(self) -> list[KrakenLedgerEntry]:
        entries: list[KrakenLedgerEntry] = []
        with self._source_path.open(encoding="utf-8") as handle:
            reader = DictReader(handle)
            for row in reader:
                entries.append(KrakenLedgerEntry.model_validate(row))
        return entries

    def _group_by_refid(self, entries: Iterable[KrakenLedgerEntry]) -> dict[str, list[KrakenLedgerEntry]]:
        grouped: dict[str, list[KrakenLedgerEntry]] = defaultdict(list)
        for entry in entries:
            grouped[entry.refid].append(entry)
        return grouped

    def _build_event(self, entries: list[KrakenLedgerEntry]) -> LedgerEvent | None:
        if not entries:
            raise ValueError("Empty Kraken ledger group cannot produce an event")

        if len(entries) == 1 and entries[0].type == "deposit":
            return self._deposit_event(entries[0])
        if len(entries) == 1 and entries[0].type == "withdrawal":
            return self._withdrawal_event(entries[0])

        raise ValueError(f"Unsupported Kraken ledger group (refid={entries[0].refid}, count={len(entries)})")

    def _deposit_event(self, entry: KrakenLedgerEntry) -> LedgerEvent:
        if entry.amount <= 0:
            raise ValueError(f"Deposit entry must have positive amount (refid={entry.refid})")

        asset_code = entry.asset.upper()
        event_type = EventType.DEPOSIT if asset_code in FIAT_ASSETS else EventType.TRANSFER

        legs = [_ledger_leg(entry, entry.amount)]
        legs.extend(_fee_legs(entry))

        return LedgerEvent(
            timestamp=entry.time,
            event_type=event_type,
            legs=legs,
        )

    def _withdrawal_event(self, entry: KrakenLedgerEntry) -> LedgerEvent:
        if entry.amount >= 0:
            raise ValueError(f"Withdrawal entry must have negative amount (refid={entry.refid})")

        asset_code = entry.asset.upper()
        event_type = EventType.WITHDRAWAL if asset_code in FIAT_ASSETS else EventType.TRANSFER

        legs = [_ledger_leg(entry, entry.amount)]
        legs.extend(_fee_legs(entry))

        return LedgerEvent(
            timestamp=entry.time,
            event_type=event_type,
            legs=legs,
        )
