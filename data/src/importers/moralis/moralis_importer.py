from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, cast

from clients.moralis import MoralisService, SyncMode, build_default_service, load_accounts
from domain.ledger import (
    AssetId,
    EventLocation,
    EventOrigin,
    EventType,
    LedgerEvent,
    LedgerLeg,
    WalletAddress,
    WalletId,
)

logger = logging.getLogger(__name__)

INGESTION_SOURCE = "moralis"

CHAIN_LOCATIONS: dict[str, EventLocation] = {
    "eth": EventLocation.ETHEREUM,
    "ethereum": EventLocation.ETHEREUM,
    "arbitrum": EventLocation.ARBITRUM,
    "base": EventLocation.BASE,
    "optimism": EventLocation.OPTIMISM,
}
NATIVE_ASSET_ID = AssetId("ETH")


def _obtain_value(transfer: dict[str, Any]) -> Decimal:
    value = Decimal(transfer["value_formatted"])
    if value.is_finite():
        return value
    if transfer["token_decimals"] is None:
        return Decimal(transfer["value"])
    else:
        raise Exception("I was to lazy to implement proper handling of token decimals and value")


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _native_transfer_key(transfer: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        transfer["from_address"].lower(),
        transfer["to_address"].lower(),
        transfer["value"],
        transfer["token_symbol"].upper(),
    )


def _dedupe_native_transfers(transfers: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    flags: dict[tuple[str, str, str, str], set[bool]] = {}
    for transfer in transfers:
        key = _native_transfer_key(transfer)
        internal = transfer.get("internal_transaction") is True
        flags.setdefault(key, set()).add(internal)

    kept_external: set[tuple[str, str, str, str]] = set()
    deduped: list[dict[str, object]] = []
    for transfer in transfers:
        key = _native_transfer_key(transfer)
        internal = transfer.get("internal_transaction") is True
        if flags.get(key) == {False, True}:
            if internal:
                continue
            if key in kept_external:
                continue
            kept_external.add(key)
        deduped.append(transfer)
    return deduped


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
        wallet_addresses = set([cast(WalletAddress, account["address"].lower()) for account in accounts])
        transactions = self.service.get_transactions(self.mode)
        events: list[LedgerEvent] = []

        for tx in transactions:
            event = self._build_event(tx, wallet_addresses)
            if event:
                events.append(event)

        events.sort(key=lambda evt: evt.timestamp)
        return events

    def _build_event(self, tx: dict[str, Any], my_wallet_addresses: set[WalletAddress]) -> LedgerEvent | None:
        legs: list[LedgerLeg] = []

        has_incoming = False
        has_outgoing = False

        chain = str(tx["chain"]).lower()
        try:
            location = CHAIN_LOCATIONS[chain]
        except KeyError as e:
            raise Exception(f"Transaction {tx['hash']} with unsupported chain: {tx['chain']}") from e

        for transfer in _dedupe_native_transfers(cast(list, tx["native_transfers"])):
            token_symbol = transfer["token_symbol"]
            assert token_symbol.upper() == NATIVE_ASSET_ID, f"Unexpected native token symbol: {token_symbol}"

            from_addr = transfer["from_address"].lower()
            to_addr = transfer["to_address"].lower()
            ours_from = from_addr in my_wallet_addresses
            ours_to = to_addr in my_wallet_addresses
            if not (ours_from or ours_to):
                continue

            quantity = _obtain_value(transfer)

            if quantity == 0:
                continue

            if ours_from:
                legs.append(
                    LedgerLeg(
                        asset_id=NATIVE_ASSET_ID,
                        quantity=-quantity,
                        wallet_id=WalletId(from_addr),
                        is_fee=False,
                    )
                )
                has_outgoing = True
            if ours_to:
                legs.append(
                    LedgerLeg(
                        asset_id=NATIVE_ASSET_ID,
                        quantity=quantity,
                        wallet_id=WalletId(to_addr),
                        is_fee=False,
                    )
                )
                has_incoming = True

        for transfer in cast(list, tx["erc20_transfers"]):
            from_addr = transfer["from_address"].lower()
            to_addr = transfer["to_address"].lower()
            ours_from = from_addr in my_wallet_addresses
            ours_to = to_addr in my_wallet_addresses
            if not (ours_from or ours_to):
                continue

            quantity = _obtain_value(transfer)

            if quantity is None or quantity == 0:
                continue

            asset_id = AssetId(transfer["address"].lower())

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

        from_addr_tx = tx["from_address"].lower()
        is_my_tx = from_addr_tx in my_wallet_addresses
        if is_my_tx:
            fee = Decimal(str(tx["transaction_fee"]))
            assert fee.is_normal(), f"Unexpected transaction_fee: {tx['transaction_fee']}"
            legs.append(
                LedgerLeg(
                    asset_id=NATIVE_ASSET_ID,
                    quantity=-fee,
                    wallet_id=WalletId(from_addr_tx),
                    is_fee=True,
                )
            )

        if has_incoming and has_outgoing:
            event_type = EventType.TRADE
        elif has_incoming:
            event_type = EventType.REWARD
        elif has_outgoing:
            event_type = EventType.WITHDRAWAL
        elif is_my_tx:
            event_type = EventType.OPERATION
        else:
            # This could be NFT drop probably (probably spam)
            return None

        return LedgerEvent(
            timestamp=_parse_timestamp(str(tx["block_timestamp"])),
            origin=EventOrigin(location=location, external_id=str(tx["hash"])),
            ingestion=INGESTION_SOURCE,
            event_type=event_type,
            legs=legs,
        )
