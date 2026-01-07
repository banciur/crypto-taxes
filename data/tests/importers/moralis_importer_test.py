from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from domain.ledger import AssetId, EventType, WalletAddress
from importers.moralis.moralis_importer import CHAIN_LOCATIONS, MoralisImporter

CHAIN = "arbitrum"
TX_HASH = "0xabc123"
BLOCK_TS = "2025-05-16T05:04:40.000Z"
WALLET = WalletAddress("0x3c9219f44ead8154dee4e0854d67601fc2334c67")
SENDER = "0xb4b8b6f88361f48403514059f1f16c8e78d61ffd"


def _build_tx(
    *,
    native_transfers: list[dict[str, object]],
    from_address: str = SENDER,
    transaction_fee: str = "0",
) -> dict[str, object]:
    return {
        "block_timestamp": BLOCK_TS,
        "chain": CHAIN,
        "hash": TX_HASH,
        "from_address": from_address,
        "native_transfers": native_transfers,
        "erc20_transfers": [],
        "transaction_fee": transaction_fee,
    }


def test_native_transfer_builds_incoming_leg() -> None:
    amount = Decimal("0.5")
    symbol = "ETH"
    transfer = {
        "from_address": SENDER,
        "to_address": WALLET,
        "value": "500000000000000000",
        "value_formatted": str(amount),
        "token_symbol": symbol,
        "internal_transaction": False,
    }
    tx = _build_tx(native_transfers=[transfer])

    importer = MoralisImporter.__new__(MoralisImporter)
    event = importer._build_event(tx, {WALLET})
    expected_timestamp = datetime.fromisoformat(BLOCK_TS.replace("Z", "+00:00")).astimezone(timezone.utc)

    assert event is not None
    assert event.event_type == EventType.REWARD
    assert event.origin.location == CHAIN_LOCATIONS[CHAIN]
    assert event.origin.external_id == TX_HASH
    assert event.timestamp == expected_timestamp

    assert len(event.legs) == 1
    leg = event.legs[0]
    assert leg.asset_id == AssetId(symbol)
    assert leg.quantity == amount
    assert leg.wallet_id == WALLET


def test_native_transfer_dedupes_internal_and_external() -> None:
    amount = Decimal("0.75")
    symbol = "ETH"
    value = "750000000000000000"
    external = {
        "from_address": SENDER,
        "to_address": WALLET,
        "value": value,
        "value_formatted": str(amount),
        "token_symbol": symbol,
        "internal_transaction": False,
    }
    internal = {
        "from_address": SENDER,
        "to_address": WALLET,
        "value": value,
        "value_formatted": str(amount),
        "token_symbol": symbol,
        "internal_transaction": True,
    }
    tx = _build_tx(native_transfers=[external, internal])

    importer = MoralisImporter.__new__(MoralisImporter)
    event = importer._build_event(tx, {WALLET})

    assert event is not None
    assert len(event.legs) == 1
    assert event.legs[0].quantity == amount


def test_fee_leg_added_for_outgoing_tx() -> None:
    fee = Decimal("0.0025")
    tx = _build_tx(
        native_transfers=[],
        from_address=WALLET,
        transaction_fee=str(fee),
    )

    importer = MoralisImporter.__new__(MoralisImporter)
    event = importer._build_event(tx, {WALLET})

    assert event is not None
    assert event.event_type == EventType.OPERATION
    assert len(event.legs) == 1
    leg = event.legs[0]
    assert leg.asset_id == AssetId("ETH")
    assert leg.quantity == -fee
    assert leg.wallet_id == WALLET
    assert leg.is_fee is True
