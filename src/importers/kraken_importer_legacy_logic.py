"""Legacy Kraken importer helpers retained for reference during the rewrite."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from domain.ledger import EventType, LedgerEvent, LedgerLeg
from importers.kraken_importer import KrakenLedgerEntry


def single_line_event(entry: KrakenLedgerEntry) -> LedgerEvent | None:
    event_type = classify_single_line(entry)
    if event_type is None:
        return None

    legs = [ledger_leg(entry, entry.amount)]
    legs.extend(fee_legs(entry))

    return LedgerEvent(
        timestamp=entry.time,
        event_type=event_type,
        legs=legs,
    )


def classify_single_line(entry: KrakenLedgerEntry) -> EventType | None:
    amount = entry.amount
    if entry.type == "deposit" and amount > 0:
        return EventType.DEPOSIT
    if entry.type == "withdrawal" and amount < 0:
        return EventType.WITHDRAWAL
    if entry.type == "transfer":
        subtype = (entry.subtype or "").lower()
        if amount > 0 and subtype in {
            "spotfromfutures",
            "stakingfromspot",
            "spotfromstaking",
            "stakingtospot",
        }:
            return EventType.DEPOSIT
        if amount < 0 and subtype in {
            "spottostaking",
        }:
            return EventType.WITHDRAWAL
        return None
    if entry.type == "staking" and amount > 0:
        return EventType.REWARD
    if entry.type == "earn" and entry.subtype == "reward" and amount > 0:
        return EventType.REWARD
    return None


def double_line_event(entries: list[KrakenLedgerEntry]) -> LedgerEvent | None:
    if is_allocation_pair(entries):
        return None

    line_types = {entry.type for entry in entries}
    subtypes = {entry.subtype for entry in entries}

    if line_types <= {"trade"}:
        return build_trade_event(entries)
    if line_types == {"spend", "receive"}:
        return build_trade_event(entries)
    if line_types == {"earn"} and subtypes == {"migration"}:
        return build_trade_event(entries)
    if line_types == {"transfer"}:
        return None

    return None


def build_trade_event(entries: list[KrakenLedgerEntry]) -> LedgerEvent:
    positives = [entry for entry in entries if entry.amount > 0]
    negatives = [entry for entry in entries if entry.amount < 0]

    if len(positives) != 1 or len(negatives) != 1:
        raise ValueError(f"Expected one positive and one negative leg for trade refid={entries[0].refid}")

    legs = [
        ledger_leg(negatives[0], negatives[0].amount),
        ledger_leg(positives[0], positives[0].amount),
    ]

    for entry in entries:
        legs.extend(fee_legs(entry))

    return LedgerEvent(
        timestamp=min(entry.time for entry in entries),
        event_type=EventType.TRADE,
        legs=legs,
    )


def fee_legs(entry: KrakenLedgerEntry) -> list[LedgerLeg]:
    if entry.fee == 0:
        return []
    return [ledger_leg(entry, entry.fee * Decimal("-1"), is_fee=True)]


def ledger_leg(entry: KrakenLedgerEntry, quantity: Decimal, *, is_fee: bool = False) -> LedgerLeg:
    return LedgerLeg(
        asset_id=entry.asset,
        quantity=quantity,
        wallet_id=wallet_id(entry.wallet),
        is_fee=is_fee,
    )


def wallet_id(wallet_name: str) -> str:
    return f"kraken::{wallet_name.strip()}"


def is_allocation_pair(entries: Iterable[KrakenLedgerEntry]) -> bool:
    entries = list(entries)
    if not entries:
        return False
    if any(entry.type != "earn" for entry in entries):
        return False
    if not {entry.subtype for entry in entries}.issubset({"allocation", "deallocation"}):
        return False
    asset_ids = {entry.asset for entry in entries}
    if len(asset_ids) != 1:
        return False
    total = sum(entry.amount for entry in entries)
    return total == 0
