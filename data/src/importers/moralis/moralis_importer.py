from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any, Iterable, Mapping, cast

from accounts import AccountRegistry
from db.ledger_corrections import LedgerCorrectionRepository
from domain.correction import LedgerCorrectionDraft
from domain.ledger import (
    AccountChainId,
    AssetId,
    EventLocation,
    EventOrigin,
    LedgerEvent,
    LedgerLeg,
    WalletAddress,
)
from services.moralis import MoralisService, SyncMode
from utils.misc import ensure_utc_datetime

logger = logging.getLogger(__name__)

INGESTION_SOURCE = "moralis"
NATIVE_ASSET_ID = AssetId("ETH")


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


def _collapse_legs(legs: Iterable[LedgerLeg]) -> list[LedgerLeg]:
    net_quantities: dict[tuple[AssetId, AccountChainId, bool], Decimal] = {}
    for leg in legs:
        key = (leg.asset_id, leg.account_chain_id, leg.is_fee)
        net_quantities[key] = net_quantities.get(key, Decimal(0)) + leg.quantity

    collapsed: list[LedgerLeg] = []
    for (asset_id, account_chain_id, is_fee), quantity in net_quantities.items():
        if quantity == 0:
            continue
        collapsed.append(
            LedgerLeg(
                asset_id=asset_id,
                quantity=quantity,
                account_chain_id=account_chain_id,
                is_fee=is_fee,
            )
        )
    return collapsed


def native_asset_id(transfer: Mapping[str, Any]) -> AssetId:
    asset_id = AssetId(str(transfer["token_symbol"]))
    assert asset_id.upper() == NATIVE_ASSET_ID, f"Unexpected native token symbol: {asset_id}"
    return NATIVE_ASSET_ID


def erc20_asset_id(transfer: Mapping[str, Any]) -> AssetId:
    token_symbol = str(transfer["token_symbol"])
    if token_symbol:
        return AssetId(token_symbol)
    return AssetId(str(transfer["address"]))


def _obtain_value(transfer: dict[str, Any]) -> Decimal:
    value = Decimal(transfer["value_formatted"])
    if value.is_finite():
        return value
    if transfer["token_decimals"] is None:
        return Decimal(transfer["value"])
    else:
        raise Exception("I was to lazy to implement proper handling of token decimals and value")


def _event_note(tx: Mapping[str, Any]) -> str | None:
    method_label = tx.get("method_label")
    if method_label is None:
        return None
    trimmed = str(method_label).strip()
    return trimmed or None


class MoralisImporter:
    def __init__(
        self,
        *,
        service: MoralisService,
        account_registry: AccountRegistry,
        correction_repository: LedgerCorrectionRepository,
        sync_mode: SyncMode = SyncMode.BUDGET,
    ) -> None:
        self.service = service
        self.account_registry = account_registry
        self.sync_mode = sync_mode
        self.correction_repository = correction_repository

    def load_events(self) -> list[LedgerEvent]:
        transactions = self.service.get_transactions(self.sync_mode)
        events: list[LedgerEvent] = []

        for tx in transactions:
            event = self._build_event(tx)
            if event is None:
                continue
            events.append(event)
            if (
                tx.get("possible_spam")
                and not self.correction_repository.has_active_source(event.event_origin)
                and not self.correction_repository.is_auto_suppressed(event.event_origin)
            ):
                self.correction_repository.create(
                    LedgerCorrectionDraft(
                        timestamp=event.timestamp,
                        sources=frozenset([event.event_origin]),
                    )
                )

        events.sort(key=lambda evt: evt.timestamp)
        return events

    def _build_transfer_legs(
        self,
        *,
        location: EventLocation,
        transfers: Iterable[Mapping[str, Any]],
        asset_id_for_transfer: Callable[[Mapping[str, Any]], AssetId],
    ) -> list[LedgerLeg]:
        legs: list[LedgerLeg] = []
        for transfer in transfers:
            asset_id = asset_id_for_transfer(transfer)
            quantity = _obtain_value(cast(dict[str, Any], transfer))
            if quantity == 0:
                continue

            from_account_chain_id = self.account_registry.resolve_owned_id(
                location=location,
                address=WalletAddress(str(transfer["from_address"]).lower()),
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

            to_account_chain_id = self.account_registry.resolve_owned_id(
                location=location,
                address=WalletAddress(str(transfer["to_address"]).lower()),
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
        return legs

    def _build_event(self, tx: Mapping[str, Any]) -> LedgerEvent | None:
        location = tx["location"]

        legs = self._build_transfer_legs(
            location=location,
            transfers=_dedupe_native_transfers(cast(list, tx["native_transfers"])),
            asset_id_for_transfer=native_asset_id,
        )

        legs.extend(
            self._build_transfer_legs(
                location=location,
                transfers=cast(list, tx["erc20_transfers"]),
                asset_id_for_transfer=erc20_asset_id,
            )
        )

        # If its comming from my account add fee leg
        from_addr_tx = tx["from_address"].lower()
        sender_account_chain_id = self.account_registry.resolve_owned_id(
            location=location,
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

        legs = _collapse_legs(legs)
        if not legs:
            # This could be NFT drop probably (probably spam)
            return None

        return LedgerEvent(
            timestamp=ensure_utc_datetime(datetime.fromisoformat(tx["block_timestamp"].replace("Z", "+00:00"))),
            event_origin=EventOrigin(location=location, external_id=str(tx["hash"])),
            ingestion=INGESTION_SOURCE,
            note=_event_note(tx),
            legs=legs,
        )
