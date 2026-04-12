from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, NamedTuple, cast

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import sessionmaker

from accounts import AccountConfig, AccountRegistry
from db.ledger_corrections import (
    CorrectionsBase,
    LedgerCorrectionAutoSuppressionOrm,
    LedgerCorrectionOrm,
    LedgerCorrectionRepository,
)
from domain.correction import LedgerCorrection
from domain.ledger import AccountChainId, AssetId
from importers.moralis.moralis_importer import (
    NATIVE_ASSET_ID,
    MoralisEventParseError,
    MoralisImporter,
    MoralisValueParseError,
    _decimal_from_atomic_value,
)
from services.moralis import MoralisService
from tests.constants import ETH, ETH_ADDRESS, ETH_TX_HASH, LOCATION, USDC

GTUSDCP = AssetId("gtusdcp")
BLOCK_TS = "2025-05-16T05:04:40.000Z"
ETH_ADDRESS_2 = "0xb4b8b6f88361f48403514059f1f16c8e78d61ffd"
NULL_ADDRESS = "0x0000000000000000000000000000000000000000"
SEQUENCER_FEE_VAULT = "0x4200000000000000000000000000000000000011"


def _build_tx(
    *,
    native_transfers: list[dict[str, object]],
    erc20_transfers: list[dict[str, object]] | None = None,
    from_address: str = ETH_ADDRESS_2,
    transaction_fee: str = "0",
    method_label: str | None = None,
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
    if method_label is not None:
        tx["method_label"] = method_label
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


def _outgoing_native_transfer(
    *,
    amount: Decimal,
    value: str,
    to_address: str,
) -> dict[str, object]:
    return {
        "from_address": ETH_ADDRESS,
        "to_address": to_address,
        "value": value,
        "value_formatted": str(amount),
        "token_symbol": "ETH",
        "internal_transaction": False,
    }


def _erc20_transfer(
    *,
    from_address: str,
    to_address: str,
    amount: Decimal,
    symbol: str,
    token: str,
    value: str = "0",
    token_decimals: str | None = None,
) -> dict[str, object]:
    transfer: dict[str, object] = {
        "from_address": from_address,
        "to_address": to_address,
        "value": value,
        "value_formatted": str(amount),
        "token_symbol": symbol,
        "address": token,
    }
    if token_decimals is not None:
        transfer["token_decimals"] = token_decimals
    return transfer


class _StubMoralisService:
    def __init__(self) -> None:
        self._transactions: list[dict[str, Any]] = []

    def set_transactions(self, transactions: list[dict[str, Any]]) -> None:
        self._transactions = transactions

    def get_transactions(self, _mode: object) -> list[dict[str, Any]]:
        return self._transactions


class _ImporterTestContext(NamedTuple):
    importer: MoralisImporter
    correction_repo: LedgerCorrectionRepository
    service: _StubMoralisService


@pytest.fixture()
def test_ctx(db_engine: Engine) -> Generator[_ImporterTestContext, None, None]:
    CorrectionsBase.metadata.create_all(db_engine)
    with sessionmaker(db_engine)() as session:
        repo = LedgerCorrectionRepository(session)
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
            correction_repository=repo,
        )
        yield _ImporterTestContext(importer=importer, correction_repo=repo, service=service)
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
    assert leg.asset_id == ETH
    assert leg.quantity == -fee
    assert leg.account_chain_id == AccountChainId(f"{LOCATION.value}:{ETH_ADDRESS}")
    assert leg.is_fee is True


def test_method_label_is_trimmed_into_event_note(test_ctx: _ImporterTestContext) -> None:
    tx = _build_tx(
        native_transfers=[_native_transfer(Decimal("0.5"))],
        method_label="  depositAll  ",
    )

    event = test_ctx.importer._build_event(tx)

    assert event is not None
    assert event.note == "depositAll"


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


def test_erc20_legs_sum_exact_atomic_values_before_collapsing(test_ctx: _ImporterTestContext) -> None:
    symbol = "USDs"
    token = "0x2ea0be86990e8dac0d09e4316bb92086f304622d"
    token_decimals = "18"
    tx = _build_tx(
        native_transfers=[],
        erc20_transfers=[
            _erc20_transfer(
                from_address=ETH_ADDRESS_2,
                to_address=ETH_ADDRESS,
                amount=Decimal("1423.5107704255972"),
                symbol=symbol,
                token=token,
                value="1423510770425597170044",
                token_decimals=token_decimals,
            ),
            _erc20_transfer(
                from_address=ETH_ADDRESS_2,
                to_address=ETH_ADDRESS,
                amount=Decimal("1.5102293352788365"),
                symbol=symbol,
                token=token,
                value="1510229335278836495",
                token_decimals=token_decimals,
            ),
            _erc20_transfer(
                from_address=ETH_ADDRESS_2,
                to_address=ETH_ADDRESS,
                amount=Decimal("175.36546888769627"),
                symbol=symbol,
                token=token,
                value="175365468887696284727",
                token_decimals=token_decimals,
            ),
        ],
    )

    event = test_ctx.importer._build_event(tx)

    expected_quantity = (
        Decimal("1423510770425597170044") + Decimal("1510229335278836495") + Decimal("175365468887696284727")
    ) / (Decimal(10) ** Decimal(token_decimals))

    assert event is not None
    assert len(event.legs) == 1
    assert event.legs[0].asset_id == AssetId(symbol)
    assert event.legs[0].quantity == expected_quantity
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
    assert non_fee_leg.asset_id == ETH
    assert fee_leg.asset_id == ETH


def test_fee_native_transfers_are_not_double_counted(test_ctx: _ImporterTestContext) -> None:
    fee_components = [
        (Decimal("0.000000000256473696"), "256473696", NULL_ADDRESS),
        (Decimal("0.000000000000781932"), "781932", SEQUENCER_FEE_VAULT),
        (Decimal("0.000000014158945734"), "14158945734", NULL_ADDRESS),
    ]
    fee = sum((amount for amount, _, _ in fee_components), Decimal(0))
    tx = _build_tx(
        native_transfers=[
            _outgoing_native_transfer(amount=amount, value=value, to_address=to_address)
            for amount, value, to_address in fee_components
        ],
        erc20_transfers=[
            _erc20_transfer(
                from_address=NULL_ADDRESS,
                to_address=ETH_ADDRESS,
                amount=Decimal("18.211177826219392142"),
                symbol="gtusdcp",
                token="0xc30ce6a5758786e0f640cc5f881dd96e9a1c5c59",
                value="18211177826219392142",
                token_decimals="18",
            ),
            _erc20_transfer(
                from_address=ETH_ADDRESS,
                to_address="0x79481c87f24a3c4332442a2e9faaf675e5f141f0",
                amount=Decimal("18.3729"),
                symbol="USDC",
                token="0x0b2c639c533813f4aa9d7837caf62653d097ff85",
                value="18372900",
                token_decimals="6",
            ),
        ],
        from_address=ETH_ADDRESS,
        transaction_fee=str(fee),
    )

    event = test_ctx.importer._build_event(tx)

    expected_account_chain_id = AccountChainId(f"{LOCATION.value}:{ETH_ADDRESS}")

    assert event is not None
    assert len(event.legs) == 3
    assert [leg for leg in event.legs if leg.asset_id == ETH and leg.is_fee is False] == []
    assert {(leg.asset_id, leg.is_fee): leg.quantity for leg in event.legs} == {
        (GTUSDCP, False): Decimal("18.211177826219392142"),
        (USDC, False): Decimal("-18.3729"),
        (ETH, True): -fee,
    }
    assert {leg.account_chain_id for leg in event.legs} == {expected_account_chain_id}


def test_non_fee_native_transfer_is_preserved_when_destination_is_not_fee_sink(
    test_ctx: _ImporterTestContext,
) -> None:
    amount = Decimal("0.0025")
    tx = _build_tx(
        native_transfers=[
            _outgoing_native_transfer(
                amount=amount,
                value="2500000000000000",
                to_address=ETH_ADDRESS_2,
            )
        ],
        from_address=ETH_ADDRESS,
        transaction_fee=str(amount),
    )

    event = test_ctx.importer._build_event(tx)

    assert event is not None
    assert len(event.legs) == 2
    assert {(leg.asset_id, leg.is_fee): leg.quantity for leg in event.legs} == {
        (ETH, False): -amount,
        (ETH, True): -amount,
    }


def test_fee_native_transfers_are_filtered_while_preserving_real_native_transfer(
    test_ctx: _ImporterTestContext,
) -> None:
    fee_components = [
        (Decimal("0.000000000256473696"), "256473696", NULL_ADDRESS),
        (Decimal("0.000000000000781932"), "781932", SEQUENCER_FEE_VAULT),
        (Decimal("0.000000014158945734"), "14158945734", NULL_ADDRESS),
    ]
    fee = sum((amount for amount, _, _ in fee_components), Decimal(0))
    transfer_amount = Decimal("0.0025")
    tx = _build_tx(
        native_transfers=[
            _outgoing_native_transfer(
                amount=fee_components[0][0], value=fee_components[0][1], to_address=fee_components[0][2]
            ),
            _outgoing_native_transfer(amount=transfer_amount, value="2500000000000000", to_address=ETH_ADDRESS_2),
            _outgoing_native_transfer(
                amount=fee_components[1][0], value=fee_components[1][1], to_address=fee_components[1][2]
            ),
            _outgoing_native_transfer(
                amount=fee_components[2][0], value=fee_components[2][1], to_address=fee_components[2][2]
            ),
        ],
        from_address=ETH_ADDRESS,
        transaction_fee=str(fee),
    )

    event = test_ctx.importer._build_event(tx)

    assert event is not None
    assert len(event.legs) == 2
    assert {(leg.asset_id, leg.is_fee): leg.quantity for leg in event.legs} == {
        (ETH, False): -transfer_amount,
        (ETH, True): -fee,
    }


def test_erc20_parse_failure_includes_transaction_context(test_ctx: _ImporterTestContext) -> None:
    symbol = "USDs"
    token = "0x2ea0be86990e8dac0d09e4316bb92086f304622d"
    tx = _build_tx(
        native_transfers=[],
        erc20_transfers=[
            {
                "from_address": ETH_ADDRESS_2,
                "to_address": ETH_ADDRESS,
                "value": "0.5",
                "value_formatted": "NaN",
                "token_symbol": symbol,
                "address": token,
                "log_index": 7,
            }
        ],
    )

    with pytest.raises(MoralisEventParseError, match=ETH_TX_HASH):
        test_ctx.importer._build_event(tx)


def test_erc20_without_decimals_falls_back_to_raw_value(test_ctx: _ImporterTestContext) -> None:
    token = "0x52903256dd18d85c2dc4a6c999907c9793ea61e3"
    tx = _build_tx(
        native_transfers=[],
        erc20_transfers=[
            {
                "from_address": "0x0000000000000000000000000000000000000000",
                "to_address": ETH_ADDRESS,
                "value": "777",
                "value_formatted": "NaN",
                "token_symbol": None,
                "address": token,
                "token_decimals": None,
            }
        ],
    )

    event = test_ctx.importer._build_event(tx)

    assert event is not None
    assert len(event.legs) == 1
    assert event.legs[0].asset_id == AssetId(token)
    assert event.legs[0].quantity == Decimal("777")
    assert event.legs[0].account_chain_id == AccountChainId(f"{LOCATION.value}:{ETH_ADDRESS}")
    assert event.legs[0].is_fee is False


def test_fee_parse_failure_includes_transaction_context(test_ctx: _ImporterTestContext) -> None:
    tx = _build_tx(
        native_transfers=[],
        from_address=ETH_ADDRESS,
        transaction_fee="NaN",
    )

    with pytest.raises(MoralisEventParseError, match=ETH_TX_HASH):
        test_ctx.importer._build_event(tx)


def test_decimal_from_atomic_value_rejects_non_integral_base_value() -> None:
    with pytest.raises(MoralisValueParseError, match="base_value"):
        _decimal_from_atomic_value("1.5", "18")


def test_load_events_marks_moralis_spam_transactions(test_ctx: _ImporterTestContext) -> None:
    tx = _build_tx(native_transfers=[_native_transfer(Decimal("0.5"))], possible_spam=True)
    test_ctx.service.set_transactions([tx])

    events = test_ctx.importer.load_events()

    assert len(events) == 1
    corrections = test_ctx.correction_repo.list()
    assert len(corrections) == 1
    assert corrections[0].sources == frozenset([events[0].event_origin])
    assert corrections[0].timestamp == events[0].timestamp
    assert corrections[0].legs == frozenset()


def test_load_events_does_not_mark_non_spam_transactions(test_ctx: _ImporterTestContext) -> None:
    tx = _build_tx(native_transfers=[_native_transfer(Decimal("0.5"))], possible_spam=False)
    test_ctx.service.set_transactions([tx])

    events = test_ctx.importer.load_events()

    assert len(events) == 1
    assert test_ctx.correction_repo.list() == []


def test_load_events_preserves_manual_spam_removals(test_ctx: _ImporterTestContext) -> None:
    tx = _build_tx(native_transfers=[_native_transfer(Decimal("0.5"))], possible_spam=True)
    test_ctx.service.set_transactions([tx])
    event = test_ctx.importer._build_event(tx)
    assert event is not None
    event_origin = event.event_origin
    test_ctx.correction_repo.create(
        LedgerCorrection(
            timestamp=event.timestamp,
            sources=frozenset([event_origin]),
        )
    )
    test_ctx.correction_repo.delete(test_ctx.correction_repo.list()[0].id)

    events = test_ctx.importer.load_events()

    assert len(events) == 1
    assert events[0].event_origin == event_origin
    assert test_ctx.correction_repo.list() == []
    assert test_ctx.correction_repo._session.execute(select(LedgerCorrectionOrm)).scalars().all() == []
    suppression_rows = (
        test_ctx.correction_repo._session.execute(select(LedgerCorrectionAutoSuppressionOrm)).scalars().all()
    )
    assert len(suppression_rows) == 1
    assert suppression_rows[0].origin_location == event_origin.location.value
    assert suppression_rows[0].origin_external_id == event_origin.external_id
