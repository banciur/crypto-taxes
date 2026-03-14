# This file is completely vibed.
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Mapping

from importers.coinbase import COINBASE_ACCOUNT_ID, CoinbaseImporter
from services.coinbase import CoinbaseAccountHistory
from services.moralis import SyncMode


class _StubCoinbaseService:
    def __init__(self, account_history: CoinbaseAccountHistory | None = None) -> None:
        self.account_history = account_history
        self.modes: list[SyncMode] = []

    def set_history(self, account_history: CoinbaseAccountHistory) -> None:
        self.account_history = account_history

    def get_history(self, sync_mode: SyncMode = SyncMode.BUDGET) -> CoinbaseAccountHistory:
        self.modes.append(sync_mode)
        assert self.account_history is not None
        return self.account_history


DEFAULT_FETCHED_AT = "2026-03-11T23:33:26Z"
DEFAULT_CREATED_AT = "2025-02-20T17:17:42Z"


def money(amount: Decimal | str, currency: str) -> dict[str, str]:
    return {"amount": str(amount), "currency": currency}


def account(account_id: str, *, name: str, currency: str) -> dict[str, object]:
    return {
        "id": account_id,
        "name": name,
        "primary": True,
        "type": "wallet",
        "balance": money("0", currency),
        "created_at": DEFAULT_FETCHED_AT,
        "updated_at": DEFAULT_FETCHED_AT,
        "resource": "account",
        "resource_path": f"/v2/accounts/{account_id}",
        "currency": {"code": currency},
        "allow_deposits": True,
        "allow_withdrawals": True,
        "portfolio_id": f"portfolio-{account_id}",
    }


def transaction(
    *,
    tx_id: str,
    tx_type: str,
    account_id: str,
    amount: Decimal | str,
    currency: str,
    created_at: str = DEFAULT_CREATED_AT,
    native_amount: Decimal | str = "0",
    native_currency: str = "EUR",
    buy: Mapping[str, object] | None = None,
    sell: Mapping[str, object] | None = None,
    trade: Mapping[str, object] | None = None,
    network: Mapping[str, object] | None = None,
    description: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "amount": money(amount, currency),
        "created_at": created_at,
        "id": tx_id,
        "native_amount": money(native_amount, native_currency),
        "resource": "transaction",
        "resource_path": f"/v2/accounts/{account_id}/transactions/{tx_id}",
        "status": "completed",
        "type": tx_type,
    }
    if buy is not None:
        payload["buy"] = buy
    if sell is not None:
        payload["sell"] = sell
    if trade is not None:
        payload["trade"] = trade
    if network is not None:
        payload["network"] = network
    if description is not None:
        payload["description"] = description
    return payload


def history(*transactions: dict[str, object]) -> CoinbaseAccountHistory:
    accounts_by_id: dict[str, dict[str, object]] = {}
    for row in transactions:
        resource_path = str(row["resource_path"])
        account_id = resource_path.split("/")[3]
        currency = str(row["amount"]["currency"])  # type: ignore[index]
        accounts_by_id.setdefault(account_id, account(account_id, name=f"{currency} Wallet", currency=currency))

    return CoinbaseAccountHistory.model_validate(
        {
            "fetched_at": DEFAULT_FETCHED_AT,
            "order": "desc",
            "account_count": len(accounts_by_id),
            "transaction_count": len(transactions),
            "accounts": list(accounts_by_id.values()),
            "transactions": list(transactions),
        }
    )


def test_trade_group_builds_two_leg_event() -> None:
    trade_id = "trade-1"
    outgoing_amount = Decimal("-10.178388")
    incoming_amount = Decimal("0.00362163")
    created_at = "2025-02-20T17:17:42Z"
    trade_payload = {
        "id": trade_id,
        "payment_method_name": "USDC Wallet",
        "fee": money("0.104855", "USDC"),
    }
    trade_out = transaction(
        tx_id="trade-out",
        tx_type="trade",
        account_id="usdc-wallet",
        amount=outgoing_amount,
        currency="USDC",
        created_at=created_at,
        native_amount="-9.71",
        trade=trade_payload,
    )
    trade_in = transaction(
        tx_id="trade-in",
        tx_type="trade",
        account_id="eth-wallet",
        amount=incoming_amount,
        currency="ETH",
        created_at=created_at,
        native_amount="9.42",
        trade=trade_payload,
    )

    service = _StubCoinbaseService(history(trade_out, trade_in))

    events = CoinbaseImporter(service=service).load_events()

    assert len(events) == 1
    event = events[0]
    assert event.event_origin.external_id == trade_id
    assert event.event_origin.location == "COINBASE"
    assert {leg.asset_id: leg.quantity for leg in event.legs} == {
        "USDC": outgoing_amount,
        "ETH": incoming_amount,
    }


def test_singleton_buy_synthesizes_quote_leg() -> None:
    buy_id = "buy-1"
    acquired_amount = Decimal("0.00228939")
    total_eur = Decimal("10.00")
    buy_row = transaction(
        tx_id="buy-row",
        tx_type="buy",
        account_id="eth-wallet",
        amount=acquired_amount,
        currency="ETH",
        created_at="2025-10-05T07:59:21Z",
        native_amount=total_eur,
        buy={
            "id": buy_id,
            "payment_method_name": "4165********5009",
            "subtotal": money("9.01", "EUR"),
            "total": money(total_eur, "EUR"),
            "fee": money("0.99", "EUR"),
        },
    )

    service = _StubCoinbaseService(history(buy_row))

    events = CoinbaseImporter(service=service).load_events()

    assert len(events) == 1
    event = events[0]
    assert event.event_origin.external_id == buy_id
    assert {leg.asset_id: leg.quantity for leg in event.legs} == {
        "ETH": acquired_amount,
        "EUR": -total_eur,
    }


def test_outgoing_send_adds_fee_leg() -> None:
    sent_amount = Decimal("-0.54099118")
    fee_amount = Decimal("0.00203700")
    send_row = transaction(
        tx_id="send-row",
        tx_type="send",
        account_id="eth-wallet",
        amount=sent_amount,
        currency="ETH",
        created_at="2020-07-26T12:18:37Z",
        native_amount="-142.94",
        network={
            "hash": "66b55963d3ca4a2aa5a090494752afb26af3e0285ec36dc068b1e32512ced38a",
            "network_name": "ethereum",
            "status": "confirmed",
            "transaction_fee": money(fee_amount, "ETH"),
        },
    )

    service = _StubCoinbaseService(history(send_row))

    events = CoinbaseImporter(service=service).load_events()

    assert len(events) == 1
    event = events[0]
    non_fee_leg = next(leg for leg in event.legs if leg.is_fee is False)
    fee_leg = next(leg for leg in event.legs if leg.is_fee is True)
    assert non_fee_leg.asset_id == "ETH"
    assert non_fee_leg.quantity == sent_amount
    assert non_fee_leg.account_chain_id == COINBASE_ACCOUNT_ID
    assert fee_leg.asset_id == "ETH"
    assert fee_leg.quantity == -fee_amount
    assert fee_leg.account_chain_id == COINBASE_ACCOUNT_ID


def test_staking_transfer_pair_is_skipped_after_eth2_aliasing() -> None:
    transfer_amount = Decimal("0.00155742")
    outgoing = transaction(
        tx_id="staking-out",
        tx_type="staking_transfer",
        account_id="eth-wallet",
        amount=-transfer_amount,
        currency="ETH",
        created_at="2024-10-25T04:34:34Z",
        native_amount="-4.93",
    )
    incoming = transaction(
        tx_id="staking-in",
        tx_type="staking_transfer",
        account_id="eth2-wallet",
        amount=transfer_amount,
        currency="ETH2",
        created_at="2024-10-25T04:34:34Z",
        native_amount="4.93",
    )

    service = _StubCoinbaseService(history(outgoing, incoming))

    events = CoinbaseImporter(service=service).load_events()

    assert events == []


def test_fiat_deposit_exchange_pass_through_pair_is_skipped() -> None:
    paired_amount = Decimal("700")
    standalone_amount = Decimal("950")
    paired_deposit = transaction(
        tx_id="fiat-in",
        tx_type="fiat_deposit",
        account_id="eur-wallet",
        amount=paired_amount,
        currency="EUR",
        created_at="2022-02-16T11:31:41Z",
        native_amount=paired_amount,
    )
    paired_exchange = transaction(
        tx_id="exchange-out",
        tx_type="exchange_deposit",
        account_id="eur-wallet",
        amount=-paired_amount,
        currency="EUR",
        created_at="2022-02-16T11:31:44Z",
        native_amount=-paired_amount,
    )
    standalone_deposit = transaction(
        tx_id="fiat-standalone",
        tx_type="fiat_deposit",
        account_id="eur-wallet",
        amount=standalone_amount,
        currency="EUR",
        created_at="2024-11-28T10:19:50Z",
        native_amount=standalone_amount,
    )

    service = _StubCoinbaseService(history(paired_deposit, paired_exchange, standalone_deposit))

    events = CoinbaseImporter(service=service).load_events()

    assert len(events) == 1
    event = events[0]
    assert event.event_origin.external_id == "fiat-standalone"
    assert len(event.legs) == 1
    assert event.legs[0].asset_id == "EUR"
    assert event.legs[0].quantity == standalone_amount


def test_wrap_asset_pair_builds_swap_event() -> None:
    wrapped_amount = Decimal("0.003312601555511600")
    source_amount = Decimal("-0.003622060000000000")
    wrapped_row = transaction(
        tx_id="wrap-in",
        tx_type="wrap_asset",
        account_id="cbeth-wallet",
        amount=wrapped_amount,
        currency="CBETH",
        created_at="2025-02-21T00:03:25Z",
        native_amount="9.45",
    )
    source_row = transaction(
        tx_id="wrap-out",
        tx_type="wrap_asset",
        account_id="staked-eth-wallet",
        amount=source_amount,
        currency="ETH",
        created_at="2025-02-21T00:03:24Z",
        native_amount="-9.47",
    )

    service = _StubCoinbaseService(history(wrapped_row, source_row))

    events = CoinbaseImporter(service=service).load_events()

    assert len(events) == 1
    event = events[0]
    assert event.event_origin.external_id == "wrap_asset:wrap-in,wrap-out"
    assert {leg.asset_id: leg.quantity for leg in event.legs} == {
        "ETH": source_amount,
        "CBETH": wrapped_amount,
    }


def test_eth_to_eth2_trade_group_is_skipped_after_aliasing() -> None:
    trade_amount = Decimal("0.04068031")
    trade_id = "eth-migration"
    trade_payload = {"id": trade_id, "payment_method_name": "ETH Wallet"}
    outgoing = transaction(
        tx_id="trade-out",
        tx_type="trade",
        account_id="eth-wallet",
        amount=-trade_amount,
        currency="ETH",
        created_at="2023-07-14T19:27:27Z",
        native_amount="-74.15",
        trade=trade_payload,
    )
    incoming = transaction(
        tx_id="trade-in",
        tx_type="trade",
        account_id="eth2-wallet",
        amount=trade_amount,
        currency="ETH2",
        created_at="2023-07-14T19:27:27Z",
        native_amount="74.15",
        trade=trade_payload,
    )

    service = _StubCoinbaseService(history(outgoing, incoming))

    events = CoinbaseImporter(service=service).load_events()

    assert events == []


def test_pro_boundary_rows_are_deferred() -> None:
    pro_row = transaction(
        tx_id="pro-in",
        tx_type="pro_withdrawal",
        account_id="usdt-wallet",
        amount="10.000000",
        currency="USDT",
        created_at="2022-08-04T09:35:52Z",
        native_amount="9.82",
    )

    service = _StubCoinbaseService(history(pro_row))

    events = CoinbaseImporter(service=service).load_events()

    assert events == []


def test_history_timestamps_are_normalized_to_utc() -> None:
    tx_id = "interest-row"
    interest_amount = Decimal("6.545894")
    interest_row = transaction(
        tx_id=tx_id,
        tx_type="interest",
        account_id="usdc-wallet",
        amount=interest_amount,
        currency="USDC",
        created_at="2024-12-04T18:02:34Z",
        native_amount="6.21",
    )

    service = _StubCoinbaseService(history(interest_row))

    events = CoinbaseImporter(service=service).load_events()

    assert len(events) == 1
    assert events[0].timestamp == datetime(2024, 12, 4, 18, 2, 34, tzinfo=timezone.utc)
