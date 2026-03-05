from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, cast

from accounts import AccountRegistry, normalize_chain
from db.corrections import SpamCorrectionRepository, SpamCorrectionSource
from domain.ledger import (
    AssetId,
    EventLocation,
    EventOrigin,
    LedgerEvent,
    LedgerLeg,
    WalletAddress,
)
from services.moralis import MoralisService, SyncMode, build_default_service

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
        spam_correction_repository: SpamCorrectionRepository | None = None,
    ) -> None:
        self.service = service or build_default_service()
        self.mode = mode or SyncMode.BUDGET
        self.spam_correction_repository = spam_correction_repository

    def load_events(self) -> list[LedgerEvent]:
        account_registry = AccountRegistry.from_path(self.service.accounts_path)
        transactions = self.service.get_transactions(self.mode)
        events: list[LedgerEvent] = []

        for tx in transactions:
            event = self._build_event(tx, account_registry)
            if event is None:
                continue
            events.append(event)
            if self.spam_correction_repository is not None and tx.get("possible_spam") is True:
                self.spam_correction_repository.mark_as_spam(
                    event.event_origin,
                    SpamCorrectionSource.AUTO_MORALIS,
                    skip_if_exists=True,
                )

        events.sort(key=lambda evt: evt.timestamp)
        return events

    def _build_event(self, tx: dict[str, Any], account_registry: AccountRegistry) -> LedgerEvent | None:
        legs: list[LedgerLeg] = []

        chain = str(tx["chain"]).lower()
        try:
            location = CHAIN_LOCATIONS[chain]
        except KeyError as e:
            raise Exception(f"Transaction {tx['hash']} with unsupported chain: {tx['chain']}") from e
        normalized_chain = normalize_chain(chain)

        for transfer in _dedupe_native_transfers(cast(list, tx["native_transfers"])):
            token_symbol = transfer["token_symbol"]
            assert token_symbol.upper() == NATIVE_ASSET_ID, f"Unexpected native token symbol: {token_symbol}"

            from_addr = transfer["from_address"].lower()
            to_addr = transfer["to_address"].lower()
            quantity = _obtain_value(transfer)
            if quantity == 0:
                continue

            from_account_chain_id = account_registry.resolve_owned_id(
                chain=normalized_chain,
                address=WalletAddress(from_addr),
            )
            if from_account_chain_id is not None:
                legs.append(
                    LedgerLeg(
                        asset_id=NATIVE_ASSET_ID,
                        quantity=-quantity,
                        account_chain_id=from_account_chain_id,
                        is_fee=False,
                    )
                )
            to_account_chain_id = account_registry.resolve_owned_id(
                chain=normalized_chain,
                address=WalletAddress(to_addr),
            )
            if to_account_chain_id is not None:
                legs.append(
                    LedgerLeg(
                        asset_id=NATIVE_ASSET_ID,
                        quantity=quantity,
                        account_chain_id=to_account_chain_id,
                        is_fee=False,
                    )
                )

        for transfer in cast(list, tx["erc20_transfers"]):
            from_addr = transfer["from_address"].lower()
            to_addr = transfer["to_address"].lower()

            quantity = _obtain_value(transfer)
            if quantity == 0:
                continue

            asset_id = AssetId(transfer["token_symbol"] if transfer["token_symbol"] else transfer["address"])

            from_account_chain_id = account_registry.resolve_owned_id(
                chain=normalized_chain,
                address=WalletAddress(from_addr),
            )
            if from_account_chain_id is not None:
                legs.append(
                    LedgerLeg(
                        asset_id=asset_id,
                        quantity=-quantity,
                        account_chain_id=from_account_chain_id,
                        is_fee=False,
                    )
                )
            to_account_chain_id = account_registry.resolve_owned_id(
                chain=normalized_chain,
                address=WalletAddress(to_addr),
            )
            if to_account_chain_id is not None:
                legs.append(
                    LedgerLeg(
                        asset_id=asset_id,
                        quantity=quantity,
                        account_chain_id=to_account_chain_id,
                        is_fee=False,
                    )
                )

        from_addr_tx = tx["from_address"].lower()
        sender_account_chain_id = account_registry.resolve_owned_id(
            chain=normalized_chain,
            address=WalletAddress(from_addr_tx),
        )
        if sender_account_chain_id is not None:
            fee = Decimal(str(tx["transaction_fee"]))
            assert fee.is_normal(), f"Unexpected transaction_fee: {tx['transaction_fee']}"
            legs.append(
                LedgerLeg(
                    asset_id=NATIVE_ASSET_ID,
                    quantity=-fee,
                    account_chain_id=sender_account_chain_id,
                    is_fee=True,
                )
            )

        if not legs:
            # This could be NFT drop probably (probably spam)
            return None

        return LedgerEvent(
            timestamp=_parse_timestamp(str(tx["block_timestamp"])),
            event_origin=EventOrigin(location=location, external_id=str(tx["hash"])),
            ingestion=INGESTION_SOURCE,
            legs=legs,
        )
