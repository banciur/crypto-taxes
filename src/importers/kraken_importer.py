from __future__ import annotations

from collections import defaultdict
from csv import DictReader
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel, Field, field_validator

from domain.ledger import LedgerEvent


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
        raise ValueError("Kraken importer event builder not implemented")
