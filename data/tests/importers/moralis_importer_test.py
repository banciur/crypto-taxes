from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, NamedTuple, cast

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import sessionmaker

from accounts import AccountConfig, AccountRegistry
from db.corrections_common import CorrectionsBase
from db.corrections_spam import SpamCorrectionOrm, SpamCorrectionRepository
from domain.ledger import AccountChainId, AssetId
from importers.moralis.moralis_importer import NATIVE_ASSET_ID, MoralisImporter
from services.moralis import MoralisService
from tests.constants import ETH_ADDRESS, ETH_TX_HASH, LOCATION

BLOCK_TS = "2025-05-16T05:04:40.000Z"
ETH_ADDRESS_2 = "0xb4b8b6f88361f48403514059f1f16c8e78d61ffd"

# This file is missing test cases and supporting functions are poorly written. Next time you touch it, fix it.


def _build_tx(
    *,
    native_transfers: list[dict[str, object]],
    erc20_transfers: list[dict[str, object]] | None = None,
    from_address: str = ETH_ADDRESS_2,
    transaction_fee: str = "0",
    possible_spam: bool | None = None,
) -> dict[str, object]:
    tx: dict[str, object] = {
        "block_timestamp": BLOCK_TS,
        "location": LOCATION,
        "hash": ETH_TX_HASH,
        "from_address": from_address,
        "native_transfers": native_transfers,
        "erc20_transfers": erc20_transfers if erc20_transfers is not None else [],
        "transaction_fee": transaction_fee,
    }
    if possible_spam is not None:
        tx["possible_spam"] = possible_spam
    return tx


def _native_transfer(amount: Decimal) -> dict[str, object]:
    return {
        "from_address": ETH_ADDRESS_2,
        "to_address": ETH_ADDRESS,
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


class _StubMoralisService:
    def __init__(self) -> None:
        self._transactions: list[dict[str, Any]] = []

    def set_transactions(self, transactions: list[dict[str, Any]]) -> None:
        self._transactions = transactions

    def get_transactions(self, _mode: object) -> list[dict[str, Any]]:
        return self._transactions


class _ImporterTestContext(NamedTuple):
    importer: MoralisImporter
    spam_repo: SpamCorrectionRepository
    service: _StubMoralisService


@pytest.fixture()
def test_ctx(db_engine: Engine) -> Generator[_ImporterTestContext, None, None]:
    CorrectionsBase.metadata.create_all(db_engine)
    with sessionmaker(db_engine)() as session:
        repo = SpamCorrectionRepository(session)
        service = _StubMoralisService()
        importer = MoralisImporter(
            service=cast(MoralisService, service),
            account_registry=AccountRegistry(
                [
                    AccountConfig(
                        name="Wallet",
                        address=ETH_ADDRESS,
                        locations=frozenset([LOCATION]),
                        skip_sync=False,
                    )
                ]
            ),
            spam_correction_repository=repo,
        )
        yield _ImporterTestContext(importer=importer, spam_repo=repo, service=service)
    CorrectionsBase.metadata.drop_all(db_engine)


def test_native_transfer_builds_incoming_leg(test_ctx: _ImporterTestContext) -> None:
    amount = Decimal("0.5")
    transfer = {
        "from_address": ETH_ADDRESS_2,
        "to_address": ETH_ADDRESS,
        "value": "500000000000000000",
        "value_formatted": str(amount),
        "token_symbol": NATIVE_ASSET_ID,
        "internal_transaction": False,
    }
    tx = _build_tx(native_transfers=[transfer])

    event = test_ctx.importer._build_event(tx)
    expected_timestamp = datetime.fromisoformat(BLOCK_TS.replace("Z", "+00:00")).astimezone(timezone.utc)

    assert event is not None
    assert event.event_origin.location == LOCATION
    assert event.event_origin.external_id == ETH_TX_HASH
    assert event.timestamp == expected_timestamp

    assert len(event.legs) == 1
    leg = event.legs[0]
    assert leg.asset_id == NATIVE_ASSET_ID
    assert leg.quantity == amount
    assert leg.account_chain_id == AccountChainId(f"{LOCATION.value}:{ETH_ADDRESS}")


def test_native_transfer_dedupes_internal_and_external(test_ctx: _ImporterTestContext) -> None:
    amount = Decimal("0.75")
    value = "750000000000000000"
    external = {
        "from_address": ETH_ADDRESS_2,
        "to_address": ETH_ADDRESS,
        "value": value,
        "value_formatted": str(amount),
        "token_symbol": NATIVE_ASSET_ID,
        "internal_transaction": False,
    }
    internal = {
        "from_address": ETH_ADDRESS_2,
        "to_address": ETH_ADDRESS,
        "value": value,
        "value_formatted": str(amount),
        "token_symbol": NATIVE_ASSET_ID,
        "internal_transaction": True,
    }
    tx = _build_tx(native_transfers=[external, internal])

    event = test_ctx.importer._build_event(tx)

    assert event is not None
    assert len(event.legs) == 1
    assert event.legs[0].quantity == amount


def test_fee_leg_added_for_outgoing_tx(test_ctx: _ImporterTestContext) -> None:
    fee = Decimal("0.0025")
    tx = _build_tx(
        native_transfers=[],
        from_address=ETH_ADDRESS,
        transaction_fee=str(fee),
    )

    event = test_ctx.importer._build_event(tx)

    assert event is not None
    assert len(event.legs) == 1
    leg = event.legs[0]
    assert leg.asset_id == AssetId("ETH")
    assert leg.quantity == -fee
    assert leg.account_chain_id == AccountChainId(f"{LOCATION.value}:{ETH_ADDRESS}")
    assert leg.is_fee is True


def test_erc20_legs_net_per_asset_and_account(test_ctx: _ImporterTestContext) -> None:
    amount_out = Decimal("1.900000317186616554")
    amount_in = Decimal("0.000000764022969882")
    symbol = "WETH"
    token = "0x4200000000000000000000000000000000000006"
    tx = _build_tx(
        native_transfers=[],
        erc20_transfers=[
            _erc20_transfer(
                from_address=ETH_ADDRESS, to_address=ETH_ADDRESS_2, amount=amount_out, symbol=symbol, token=token
            ),
            _erc20_transfer(
                from_address=ETH_ADDRESS_2, to_address=ETH_ADDRESS, amount=amount_in, symbol=symbol, token=token
            ),
        ],
    )

    event = test_ctx.importer._build_event(tx)

    assert event is not None
    assert len(event.legs) == 1
    assert event.legs[0].asset_id == AssetId(symbol)
    assert event.legs[0].quantity == amount_in - amount_out
    assert event.legs[0].account_chain_id == AccountChainId(f"{LOCATION.value}:{ETH_ADDRESS}")
    assert event.legs[0].is_fee is False


def test_collapse_keeps_fee_and_non_fee_legs_separate(test_ctx: _ImporterTestContext) -> None:
    amount = Decimal("0.5")
    fee = Decimal("0.0025")
    tx = _build_tx(
        native_transfers=[
            {
                "from_address": ETH_ADDRESS,
                "to_address": ETH_ADDRESS_2,
                "value": "500000000000000000",
                "value_formatted": str(amount),
                "token_symbol": NATIVE_ASSET_ID,
                "internal_transaction": False,
            }
        ],
        from_address=ETH_ADDRESS,
        transaction_fee=str(fee),
    )

    event = test_ctx.importer._build_event(tx)

    assert event is not None
    assert len(event.legs) == 2
    non_fee_leg = next(leg for leg in event.legs if leg.is_fee is False)
    fee_leg = next(leg for leg in event.legs if leg.is_fee is True)
    assert non_fee_leg.quantity == -amount
    assert fee_leg.quantity == -fee
    assert non_fee_leg.asset_id == AssetId("ETH")
    assert fee_leg.asset_id == AssetId("ETH")


def test_load_events_marks_moralis_spam_transactions(test_ctx: _ImporterTestContext) -> None:
    tx = _build_tx(native_transfers=[_native_transfer(Decimal("0.5"))], possible_spam=True)
    test_ctx.service.set_transactions([tx])

    events = test_ctx.importer.load_events()

    assert len(events) == 1
    spam_events = test_ctx.spam_repo.list()
    assert len(spam_events) == 1
    assert spam_events[0].event_origin == events[0].event_origin


def test_load_events_does_not_mark_non_spam_transactions(test_ctx: _ImporterTestContext) -> None:
    tx = _build_tx(native_transfers=[_native_transfer(Decimal("0.5"))], possible_spam=False)
    test_ctx.service.set_transactions([tx])

    events = test_ctx.importer.load_events()

    assert len(events) == 1
    assert test_ctx.spam_repo.list() == []


def test_load_events_preserves_manual_spam_removals(test_ctx: _ImporterTestContext) -> None:
    tx = _build_tx(native_transfers=[_native_transfer(Decimal("0.5"))], possible_spam=True)
    test_ctx.service.set_transactions([tx])
    event = test_ctx.importer._build_event(tx)
    assert event is not None
    event_origin = event.event_origin
    test_ctx.spam_repo.mark_as_spam(event_origin=event_origin)
    test_ctx.spam_repo.remove_spam_mark(event_origin)

    events = test_ctx.importer.load_events()

    assert len(events) == 1
    assert events[0].event_origin == event_origin
    assert test_ctx.spam_repo.list() == []
    row = test_ctx.spam_repo._session.execute(select(SpamCorrectionOrm)).scalar_one()
    assert row.is_deleted is True
