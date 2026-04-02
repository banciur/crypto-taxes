from __future__ import annotations

import logging
from abc import ABC
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal, InvalidOperation
from functools import partial
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
FEE_NATIVE_TRANSFER_DESTINATIONS = frozenset(
    [
        WalletAddress("0x0000000000000000000000000000000000000000"),
        WalletAddress("0x4200000000000000000000000000000000000011"),
    ]
)


class MoralisImporterError(Exception, ABC):
    pass


class MoralisValueParseError(MoralisImporterError):
    pass


class MoralisEventParseError(MoralisImporterError):
    pass


def _normalize_address(raw_value: object) -> str:
    return str(raw_value).strip().lower()


def _wallet_address(raw_value: object) -> WalletAddress:
    return WalletAddress(_normalize_address(raw_value))


def _native_transfer_key(transfer: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        _normalize_address(transfer["from_address"]),
        _normalize_address(transfer["to_address"]),
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
    token_symbol = str(transfer.get("token_symbol") or "").strip()
    if token_symbol:
        return AssetId(token_symbol)
    return AssetId(_normalize_address(transfer["address"]))


def _parse_decimal_string(*, raw_value: object, field_name: str, require_integral: bool) -> Decimal:
    if not isinstance(raw_value, str):
        raise MoralisValueParseError(f"Unexpected {field_name} type: {type(raw_value)}")

    try:
        value = Decimal(raw_value)
    except InvalidOperation as exc:
        raise MoralisValueParseError(f"Unexpected {field_name}: {raw_value}") from exc

    if not value.is_finite() or (require_integral and value != value.to_integral_value()):
        raise MoralisValueParseError(f"Unexpected {field_name}: {raw_value}")

    return value


def _decimal_from_atomic_value(base_value: str, decimals: str) -> Decimal:
    base_dec = _parse_decimal_string(raw_value=base_value, field_name="base_value", require_integral=True)
    decimals_dec = _parse_decimal_string(raw_value=decimals, field_name="decimals", require_integral=True)

    return base_dec / (Decimal(10) ** decimals_dec)


def _obtain_value(transfer: Mapping[str, Any]) -> Decimal:
    token_decimals = transfer.get("token_decimals")
    if token_decimals is not None:
        return _decimal_from_atomic_value(transfer["value"], token_decimals)

    try:
        return _parse_decimal_string(
            raw_value=transfer["value_formatted"],
            field_name="value_formatted",
            require_integral=False,
        )
    except MoralisValueParseError:
        return _parse_decimal_string(
            raw_value=transfer["value"],
            field_name="value",
            require_integral=True,
        )


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

    def _legs_for_transfer(
        self,
        transfer: Mapping[str, Any],
        *,
        location: EventLocation,
        asset_id_for_transfer: Callable[[Mapping[str, Any]], AssetId],
    ) -> Iterable[LedgerLeg]:
        quantity = _obtain_value(transfer)
        if quantity == 0:
            return ()

        legs = []
        asset_id = asset_id_for_transfer(transfer)
        resolve_owned_id = partial(self.account_registry.resolve_owned_id, location=location)

        if from_address_chain_id := resolve_owned_id(address=_wallet_address(transfer["from_address"])):
            legs.append(
                LedgerLeg(
                    asset_id=asset_id,
                    quantity=-quantity,
                    account_chain_id=from_address_chain_id,
                    is_fee=False,
                )
            )

        if to_address_chain_id := resolve_owned_id(address=_wallet_address(transfer["to_address"])):
            legs.append(
                LedgerLeg(
                    asset_id=asset_id,
                    quantity=quantity,
                    account_chain_id=to_address_chain_id,
                    is_fee=False,
                )
            )

        return legs

    def _filter_fee_native_transfers(
        self,
        *,
        location: EventLocation,
        tx: Mapping[str, Any],
        native_transfers: list[dict[str, Any]],
        fee: Decimal,
    ) -> list[dict[str, Any]]:
        """Moralis can expose L2 gas breakdown as synthetic native transfers alongside
        transaction_fee; drop only that fee subset so real native transfers from the same tx still import.
        """

        sender_address = _wallet_address(tx["from_address"])
        fee_total = Decimal(0)
        filtered_transfers: list[dict[str, Any]] = []
        for transfer in native_transfers:
            to_address = _wallet_address(transfer["to_address"])
            is_fee_transfer = (
                _wallet_address(transfer["from_address"]) == sender_address
                and to_address in FEE_NATIVE_TRANSFER_DESTINATIONS
                and self.account_registry.resolve_owned_id(location=location, address=to_address) is None
            )
            if is_fee_transfer:
                fee_total += _obtain_value(transfer)
            else:
                filtered_transfers.append(transfer)

        return filtered_transfers if fee_total == fee else native_transfers

    def _build_event(self, tx: Mapping[str, Any]) -> LedgerEvent | None:
        location = tx["location"]
        tx_hash = str(tx["hash"])
        native_transfers = _dedupe_native_transfers(cast(list, tx["native_transfers"]))

        try:
            legs: list[LedgerLeg] = []
            if sender_account_chain_id := self.account_registry.resolve_owned_id(
                location=location,
                address=_wallet_address(tx["from_address"]),
            ):
                fee = _parse_decimal_string(
                    raw_value=tx["transaction_fee"],
                    field_name="transaction_fee",
                    require_integral=False,
                )
                assert fee >= 0, f"Unexpected negative transaction fee: {fee}"
                legs.append(
                    LedgerLeg(
                        asset_id=NATIVE_ASSET_ID,
                        quantity=-fee,
                        account_chain_id=sender_account_chain_id,
                        is_fee=True,
                    )
                )

                native_transfers = self._filter_fee_native_transfers(
                    location=location,
                    tx=tx,
                    native_transfers=native_transfers,
                    fee=fee,
                )

            legs_for_transfer = partial(self._legs_for_transfer, location=location)

            for transfer in native_transfers:
                legs.extend(legs_for_transfer(transfer, asset_id_for_transfer=native_asset_id))

            for transfer in cast(list, tx["erc20_transfers"]):
                legs.extend(legs_for_transfer(transfer, asset_id_for_transfer=erc20_asset_id))
        except MoralisValueParseError as exc:
            raise MoralisEventParseError(
                f"Failed to parse Moralis event numeric field for tx={tx_hash} location={location.value}: {exc}"
            ) from exc

        legs = _collapse_legs(legs)
        if not legs:
            # This could be NFT drop probably (probably spam)
            return None

        return LedgerEvent(
            timestamp=ensure_utc_datetime(datetime.fromisoformat(tx["block_timestamp"].replace("Z", "+00:00"))),
            event_origin=EventOrigin(location=location, external_id=str(tx["hash"])),
            ingestion=INGESTION_SOURCE,
            note=str(tx.get("method_label") or "").strip() or None,
            legs=legs,
        )
