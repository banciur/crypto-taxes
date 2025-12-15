from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, cast

from clients.moralis import Account, MoralisService, SyncMode, build_default_service, load_accounts
from domain.ledger import AssetId, EventLocation, EventOrigin, EventType, LedgerEvent, LedgerLeg, WalletId

logger = logging.getLogger(__name__)

INGESTION_SOURCE = "moralis"

CHAIN_LOCATIONS: dict[str, EventLocation] = {
    "eth": EventLocation.ETHEREUM,
    "ethereum": EventLocation.ETHEREUM,
    "arbitrum": EventLocation.ARBITRUM,
    "base": EventLocation.BASE,
    "optimism": EventLocation.OPTIMISM,
}


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _decode_quantity(entry: dict[str, object]) -> Decimal | None:
    def _parse_decimal(raw: object) -> Decimal | None:
        try:
            val = Decimal(str(raw))
        except Exception:
            return None
        return val if val.is_finite() else None

    value_formatted = entry.get("value_formatted")
    if value_formatted is not None:
        parsed = _parse_decimal(value_formatted)
        if parsed is None:
            return None
        return parsed

    value = _parse_decimal(entry.get("value"))
    if value is None:
        return None

    decimals_raw = entry.get("token_decimals")
    try:
        decimals = int(str(decimals_raw)) if decimals_raw is not None else 0
    except (TypeError, ValueError):
        decimals = 0
    if decimals:
        scaled = value / (Decimal(10) ** decimals)
        return scaled if scaled.is_finite() else None
    return value


def _collect_wallets(accounts: Iterable[Account]) -> set[str]:
    wallets: set[str] = set()
    for account in accounts:
        address = str(account["address"]).lower()
        wallets.add(address)
    return wallets


class MoralisImporter:
    def __init__(
        self,
        service: MoralisService | None = None,
        *,
        mode: SyncMode | None = None,
    ) -> None:
        self.service = service or build_default_service()
        self.mode = mode or SyncMode.BUDGET

    def load_events(self) -> list[LedgerEvent]:
        accounts = load_accounts(self.service.accounts_path)
        wallets = _collect_wallets(accounts)
        transactions = self.service.get_transactions(self.mode)
        events: list[LedgerEvent] = []

        for tx in transactions:
            event = self._build_event(tx, wallets)
            if event:
                events.append(event)

        events.sort(key=lambda evt: evt.timestamp)
        return events

    def _build_event(self, tx: dict[str, object], wallets: set[str]) -> LedgerEvent | None:
        chain_raw = tx.get("chain")
        if not chain_raw:
            return None
        chain = str(chain_raw).lower()
        location = CHAIN_LOCATIONS.get(chain)
        if location is None:
            logger.info("Skipping transaction with unsupported chain: %s", chain_raw)
            return None

        hash_ = str(tx["hash"])
        timestamp = _parse_timestamp(str(tx["block_timestamp"]))

        erc20_transfers = cast(list[dict[str, Any]], tx.get("erc20_transfers") or [])
        legs: list[LedgerLeg] = []
        has_incoming = False
        has_outgoing = False

        for transfer in erc20_transfers:
            from_addr = str(transfer.get("from_address") or "").lower()
            to_addr = str(transfer.get("to_address") or "").lower()
            ours_from = from_addr in wallets
            ours_to = to_addr in wallets
            if not (ours_from or ours_to):
                continue

            quantity = _decode_quantity(transfer)
            if quantity is None or quantity == 0:
                continue

            asset_id = AssetId(str(transfer["address"]).lower())

            if ours_from:
                legs.append(
                    LedgerLeg(
                        asset_id=asset_id,
                        quantity=-quantity,
                        wallet_id=WalletId(from_addr),
                        is_fee=False,
                    )
                )
                has_outgoing = True
            if ours_to:
                legs.append(
                    LedgerLeg(
                        asset_id=asset_id,
                        quantity=quantity,
                        wallet_id=WalletId(to_addr),
                        is_fee=False,
                    )
                )
                has_incoming = True

        event_type: EventType | None
        if not legs:
            # Currently we only handle ERC20 transfers; skip empty events.
            return None
        else:
            if has_incoming and has_outgoing:
                event_type = EventType.TRADE
            elif has_incoming:
                event_type = EventType.REWARD
            else:
                event_type = EventType.WITHDRAWAL

        origin = EventOrigin(location=location, external_id=hash_)

        return LedgerEvent(
            timestamp=timestamp,
            origin=origin,
            ingestion=INGESTION_SOURCE,
            event_type=event_type,
            legs=legs,
        )
