from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from sqlalchemy import select

from accounts import AccountConfig, AccountRegistry
from db.corrections import SpamCorrectionOrm, SpamCorrectionRepository, SpamCorrectionSource, init_corrections_db
from domain.ledger import AccountChainId, AssetId, ChainId, EventOrigin, WalletAddress
from importers.moralis.moralis_importer import CHAIN_LOCATIONS, MoralisImporter
from services.moralis import MoralisService

CHAIN = "arbitrum"
TX_HASH = "0xabc123"
BLOCK_TS = "2025-05-16T05:04:40.000Z"
WALLET = WalletAddress("0x64c74B53C247D176c5fefd1E239F92B23dF434BF".lower())
SENDER = "0xb4b8b6f88361f48403514059f1f16c8e78d61ffd"


class _StubMoralisService:
    def __init__(self, *, transactions: list[dict[str, Any]]) -> None:
        self._transactions = transactions

    def get_transactions(self, _mode: object) -> list[dict[str, Any]]:
        return self._transactions


def _registry() -> AccountRegistry:
    return AccountRegistry(
        [
            AccountConfig(
                name="Wallet",
                address=WALLET,
                chains=frozenset([ChainId(CHAIN)]),
                skip_sync=False,
            )
        ]
    )


def _build_tx(
    *,
    native_transfers: list[dict[str, object]],
    erc20_transfers: list[dict[str, object]] | None = None,
    from_address: str = SENDER,
    transaction_fee: str = "0",
) -> dict[str, object]:
    return {
        "block_timestamp": BLOCK_TS,
        "chain": CHAIN,
        "hash": TX_HASH,
        "from_address": from_address,
        "native_transfers": native_transfers,
        "erc20_transfers": erc20_transfers if erc20_transfers is not None else [],
        "transaction_fee": transaction_fee,
    }


def _native_transfer(amount: Decimal) -> dict[str, object]:
    return {
        "from_address": SENDER,
        "to_address": WALLET,
        "value": "500000000000000000",
        "value_formatted": str(amount),
        "token_symbol": "ETH",
        "internal_transaction": False,
    }


def _erc20_transfer(
    *, from_address: str, to_address: str, amount: Decimal, symbol: str, token: str
) -> dict[str, object]:
    return {
        "from_address": from_address,
        "to_address": to_address,
        "value": "0",
        "value_formatted": str(amount),
        "token_symbol": symbol,
        "address": token,
    }


def _marker_row(repo: SpamCorrectionRepository) -> SpamCorrectionOrm:
    stmt = select(SpamCorrectionOrm)
    row = repo._session.execute(stmt).scalar_one_or_none()
    assert row is not None
    return row


def _importer_for_build() -> MoralisImporter:
    return MoralisImporter(
        service=cast(MoralisService, _StubMoralisService(transactions=[])),
        account_registry=_registry(),
    )


def _event_origin(tx: dict[str, object]) -> EventOrigin:
    event = _importer_for_build()._build_event(tx)
    assert event is not None
    return event.event_origin


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

    importer = _importer_for_build()
    event = importer._build_event(tx)
    expected_timestamp = datetime.fromisoformat(BLOCK_TS.replace("Z", "+00:00")).astimezone(timezone.utc)

    assert event is not None
    assert event.event_origin.location == CHAIN_LOCATIONS[CHAIN]
    assert event.event_origin.external_id == TX_HASH
    assert event.timestamp == expected_timestamp

    assert len(event.legs) == 1
    leg = event.legs[0]
    assert leg.asset_id == AssetId(symbol)
    assert leg.quantity == amount
    assert leg.account_chain_id == AccountChainId(f"{CHAIN}:{WALLET}")


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

    importer = _importer_for_build()
    event = importer._build_event(tx)

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

    importer = _importer_for_build()
    event = importer._build_event(tx)

    assert event is not None
    assert len(event.legs) == 1
    leg = event.legs[0]
    assert leg.asset_id == AssetId("ETH")
    assert leg.quantity == -fee
    assert leg.account_chain_id == AccountChainId(f"{CHAIN}:{WALLET}")
    assert leg.is_fee is True


def test_erc20_legs_net_per_asset_and_account() -> None:
    amount_out = Decimal("1.900000317186616554")
    amount_in = Decimal("0.000000764022969882")
    symbol = "WETH"
    token = "0x4200000000000000000000000000000000000006"
    tx = _build_tx(
        native_transfers=[],
        erc20_transfers=[
            _erc20_transfer(from_address=WALLET, to_address=SENDER, amount=amount_out, symbol=symbol, token=token),
            _erc20_transfer(from_address=SENDER, to_address=WALLET, amount=amount_in, symbol=symbol, token=token),
        ],
    )

    importer = _importer_for_build()
    event = importer._build_event(tx)

    assert event is not None
    assert len(event.legs) == 1
    assert event.legs[0].asset_id == AssetId(symbol)
    assert event.legs[0].quantity == amount_in - amount_out
    assert event.legs[0].account_chain_id == AccountChainId(f"{CHAIN}:{WALLET}")
    assert event.legs[0].is_fee is False


def test_collapse_keeps_fee_and_non_fee_legs_separate() -> None:
    amount = Decimal("0.5")
    fee = Decimal("0.0025")
    tx = _build_tx(
        native_transfers=[
            {
                "from_address": WALLET,
                "to_address": SENDER,
                "value": "500000000000000000",
                "value_formatted": str(amount),
                "token_symbol": "ETH",
                "internal_transaction": False,
            }
        ],
        from_address=WALLET,
        transaction_fee=str(fee),
    )

    importer = _importer_for_build()
    event = importer._build_event(tx)

    assert event is not None
    assert len(event.legs) == 2
    non_fee_leg = next(leg for leg in event.legs if leg.is_fee is False)
    fee_leg = next(leg for leg in event.legs if leg.is_fee is True)
    assert non_fee_leg.quantity == -amount
    assert fee_leg.quantity == -fee
    assert non_fee_leg.asset_id == AssetId("ETH")
    assert fee_leg.asset_id == AssetId("ETH")


def test_load_events_marks_moralis_spam_transactions(tmp_path: Path) -> None:
    amount = Decimal("0.5")
    tx = _build_tx(native_transfers=[_native_transfer(amount)])
    tx["possible_spam"] = True
    repo = SpamCorrectionRepository(init_corrections_db(db_path=tmp_path / "corrections.db", reset=True))
    service = _StubMoralisService(transactions=[tx])
    importer = MoralisImporter(
        service=cast(MoralisService, service),
        account_registry=_registry(),
        spam_correction_repository=repo,
    )

    events = importer.load_events()

    assert len(events) == 1
    assert repo.list()[0].event_origin == events[0].event_origin
    assert _marker_row(repo).source == SpamCorrectionSource.AUTO_MORALIS.value


def test_load_events_does_not_mark_non_spam_transactions(tmp_path: Path) -> None:
    amount = Decimal("0.5")
    tx = _build_tx(native_transfers=[_native_transfer(amount)])
    tx["possible_spam"] = False
    repo = SpamCorrectionRepository(init_corrections_db(db_path=tmp_path / "corrections.db", reset=True))
    service = _StubMoralisService(transactions=[tx])
    importer = MoralisImporter(
        service=cast(MoralisService, service),
        account_registry=_registry(),
        spam_correction_repository=repo,
    )

    events = importer.load_events()

    assert len(events) == 1
    assert repo.list() == []


def test_load_events_preserves_manual_spam_removals(tmp_path: Path) -> None:
    amount = Decimal("0.5")
    tx = _build_tx(native_transfers=[_native_transfer(amount)])
    tx["possible_spam"] = True
    repo = SpamCorrectionRepository(init_corrections_db(db_path=tmp_path / "corrections.db", reset=True))
    event_origin = _event_origin(tx)
    repo.mark_as_spam(event_origin=event_origin, source=SpamCorrectionSource.MANUAL)
    repo.remove_spam_mark(event_origin)
    service = _StubMoralisService(transactions=[tx])
    importer = MoralisImporter(
        service=cast(MoralisService, service),
        account_registry=_registry(),
        spam_correction_repository=repo,
    )

    events = importer.load_events()

    assert len(events) == 1
    assert events[0].event_origin == event_origin
    assert repo.list() == []
    row = _marker_row(repo)
    assert row.is_deleted is True
    assert row.source == SpamCorrectionSource.MANUAL.value
