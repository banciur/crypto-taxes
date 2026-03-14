# This file is completely vibed.
from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import timedelta, timezone
from decimal import Decimal
from typing import Protocol, TypeVar

from domain.ledger import AccountChainId, AssetId, EventLocation, EventOrigin, LedgerEvent, LedgerLeg
from services.coinbase import CoinbaseAccountHistory, CoinbaseMoney, CoinbaseTransaction
from services.moralis import SyncMode

logger = logging.getLogger(__name__)

COINBASE_ACCOUNT_ID = AccountChainId("coinbase")
INGESTION = "coinbase_api"

_ASSET_ALIASES = {
    "ETH2": "ETH",
}
_WRAP_PAIR_MAX_DELTA = timedelta(seconds=2)
_INTERNAL_PAIR_MAX_DELTA = timedelta(seconds=2)
_EXCHANGE_PASS_THROUGH_MAX_DELTA = timedelta(seconds=10)
_DEFERRED_TYPES = frozenset({"pro_deposit", "pro_withdrawal"})
_SINGLE_ROW_TYPES = frozenset(
    {
        "send",
        "staking_reward",
        "earn_payout",
        "interest",
        "tx",
        "fiat_deposit",
        "fiat_withdrawal",
    }
)
_KNOWN_TYPES = (
    _SINGLE_ROW_TYPES
    | _DEFERRED_TYPES
    | {
        "buy",
        "exchange_deposit",
        "retail_eth2_deprecation",
        "sell",
        "staking_transfer",
        "trade",
        "wrap_asset",
    }
)

_TxT = TypeVar("_TxT", bound=CoinbaseTransaction)


class CoinbaseHistoryProvider(Protocol):
    def get_history(self, sync_mode: SyncMode = SyncMode.BUDGET) -> CoinbaseAccountHistory: ...


def _normalize_asset_id(asset_id: str) -> AssetId:
    code = asset_id.upper()
    return AssetId(_ASSET_ALIASES.get(code, code))


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


def _positive_quote_money(total: CoinbaseMoney | None, fallback: CoinbaseMoney) -> CoinbaseMoney:
    if total is not None:
        return total
    return CoinbaseMoney(amount=abs(fallback.amount), currency=fallback.currency)


def _pair_transactions(
    positives: Iterable[_TxT],
    negatives: Iterable[_TxT],
    *,
    max_delta: timedelta,
    matches: Callable[[_TxT, _TxT], bool],
) -> tuple[list[tuple[_TxT, _TxT]], list[_TxT]]:
    ordered_positives = sorted(positives, key=lambda tx: tx.created_at)
    ordered_negatives = sorted(negatives, key=lambda tx: tx.created_at)

    used_negative_ids: set[str] = set()
    pairs: list[tuple[_TxT, _TxT]] = []
    leftovers: list[_TxT] = []

    for positive in ordered_positives:
        best_match: _TxT | None = None
        best_delta: timedelta | None = None
        for negative in ordered_negatives:
            if negative.id in used_negative_ids:
                continue
            if not matches(positive, negative):
                continue

            delta = abs(positive.created_at - negative.created_at)
            if delta > max_delta:
                continue
            if best_delta is None or delta < best_delta:
                best_match = negative
                best_delta = delta

        if best_match is None:
            leftovers.append(positive)
            continue

        used_negative_ids.add(best_match.id)
        pairs.append((positive, best_match))

    leftovers.extend(negative for negative in ordered_negatives if negative.id not in used_negative_ids)
    return pairs, leftovers


class CoinbaseImporter:
    def __init__(
        self,
        *,
        service: CoinbaseHistoryProvider,
        sync_mode: SyncMode = SyncMode.BUDGET,
    ) -> None:
        self.service = service
        self.sync_mode = sync_mode

    def load_events(self) -> list[LedgerEvent]:
        history = self.service.get_history(self.sync_mode)
        transactions_by_type: dict[str, list[CoinbaseTransaction]] = defaultdict(list)
        deferred_rows = 0

        for transaction in history.transactions:
            if transaction.type in _DEFERRED_TYPES:
                deferred_rows += 1
                continue
            if transaction.type not in _KNOWN_TYPES:
                raise ValueError(f"Unsupported Coinbase transaction type={transaction.type} id={transaction.id}")
            transactions_by_type[transaction.type].append(transaction)

        fiat_deposits = transactions_by_type["fiat_deposit"]
        exchange_deposits = transactions_by_type["exchange_deposit"]
        _, leftover_fiat_rows, leftover_exchange_rows = self._pair_fiat_exchange_transfers(
            fiat_deposits,
            exchange_deposits,
        )
        if leftover_exchange_rows:
            raise ValueError(
                "Unsupported Coinbase exchange_deposit rows without matching fiat_deposit: "
                + ", ".join(tx.id for tx in leftover_exchange_rows)
            )
        transactions_by_type["fiat_deposit"] = leftover_fiat_rows

        self._assert_internal_pairs_fully_matched(
            transactions_by_type["staking_transfer"],
            label="staking_transfer",
        )
        self._assert_internal_pairs_fully_matched(
            transactions_by_type["retail_eth2_deprecation"],
            label="retail_eth2_deprecation",
        )

        wrap_pairs, leftover_wrap_rows = self._pair_wrap_rows(transactions_by_type["wrap_asset"])
        if leftover_wrap_rows:
            raise ValueError(
                "Unsupported Coinbase wrap_asset rows without a nearby counterpart: "
                + ", ".join(tx.id for tx in leftover_wrap_rows)
            )

        events: list[LedgerEvent] = []

        for grouped_rows in self._group_by_nested_id(transactions_by_type["buy"], "buy").values():
            event = self._build_buy_event(grouped_rows)
            if event is not None:
                events.append(event)

        for grouped_rows in self._group_by_nested_id(transactions_by_type["sell"], "sell").values():
            event = self._build_sell_event(grouped_rows)
            if event is not None:
                events.append(event)

        for grouped_rows in self._group_by_nested_id(transactions_by_type["trade"], "trade").values():
            event = self._build_trade_event(grouped_rows)
            if event is not None:
                events.append(event)

        for positive_row, negative_row in wrap_pairs:
            event = self._build_wrap_event(positive_row, negative_row)
            if event is not None:
                events.append(event)

        single_row_transactions = [tx for tx_type in _SINGLE_ROW_TYPES for tx in transactions_by_type[tx_type]]
        for transaction in sorted(single_row_transactions, key=lambda tx: tx.created_at):
            event = self._build_single_row_event(transaction)
            if event is not None:
                events.append(event)

        if deferred_rows:
            logger.info("Skipping %d deferred Coinbase Pro boundary rows", deferred_rows)

        events.sort(key=lambda event: event.timestamp)
        return events

    def _group_by_nested_id(
        self,
        transactions: Iterable[CoinbaseTransaction],
        nested_attr: str,
    ) -> dict[str, list[CoinbaseTransaction]]:
        grouped: dict[str, list[CoinbaseTransaction]] = defaultdict(list)
        for transaction in transactions:
            nested = getattr(transaction, nested_attr)
            if nested is None:
                raise ValueError(
                    f"Coinbase transaction type={transaction.type} id={transaction.id} is missing {nested_attr} payload"
                )
            grouped[nested.id].append(transaction)
        return grouped

    def _pair_fiat_exchange_transfers(
        self,
        fiat_deposits: Iterable[CoinbaseTransaction],
        exchange_deposits: Iterable[CoinbaseTransaction],
    ) -> tuple[
        list[tuple[CoinbaseTransaction, CoinbaseTransaction]], list[CoinbaseTransaction], list[CoinbaseTransaction]
    ]:
        pairs, leftovers = _pair_transactions(
            positives=fiat_deposits,
            negatives=exchange_deposits,
            max_delta=_EXCHANGE_PASS_THROUGH_MAX_DELTA,
            matches=lambda positive, negative: (
                positive.account_id == negative.account_id
                and positive.amount.currency == negative.amount.currency
                and positive.amount.amount == abs(negative.amount.amount)
            ),
        )
        leftover_fiat_rows = [tx for tx in leftovers if tx.type == "fiat_deposit"]
        leftover_exchange_rows = [tx for tx in leftovers if tx.type == "exchange_deposit"]
        return pairs, leftover_fiat_rows, leftover_exchange_rows

    def _assert_internal_pairs_fully_matched(
        self,
        transactions: Iterable[CoinbaseTransaction],
        *,
        label: str,
    ) -> None:
        positive_rows = [tx for tx in transactions if tx.amount.amount > 0]
        negative_rows = [tx for tx in transactions if tx.amount.amount < 0]
        _, leftovers = _pair_transactions(
            positives=positive_rows,
            negatives=negative_rows,
            max_delta=_INTERNAL_PAIR_MAX_DELTA,
            matches=lambda positive, negative: (
                _normalize_asset_id(positive.amount.currency) == _normalize_asset_id(negative.amount.currency)
                and positive.amount.amount == abs(negative.amount.amount)
            ),
        )
        if leftovers:
            raise ValueError(
                f"Unsupported Coinbase {label} rows without a nearby opposite leg: "
                + ", ".join(tx.id for tx in leftovers)
            )

    def _pair_wrap_rows(
        self,
        transactions: Iterable[CoinbaseTransaction],
    ) -> tuple[list[tuple[CoinbaseTransaction, CoinbaseTransaction]], list[CoinbaseTransaction]]:
        positive_rows = [tx for tx in transactions if tx.amount.amount > 0]
        negative_rows = [tx for tx in transactions if tx.amount.amount < 0]
        return _pair_transactions(
            positives=positive_rows,
            negatives=negative_rows,
            max_delta=_WRAP_PAIR_MAX_DELTA,
            matches=lambda positive, negative: True,
        )

    def _synthetic_pair_origin(self, prefix: str, transactions: Iterable[CoinbaseTransaction]) -> str:
        member_ids = ",".join(sorted(transaction.id for transaction in transactions))
        return f"{prefix}:{member_ids}"

    def _amount_leg(self, money: CoinbaseMoney, *, quantity: Decimal | None = None, is_fee: bool = False) -> LedgerLeg:
        amount = money.amount if quantity is None else quantity
        return LedgerLeg(
            asset_id=_normalize_asset_id(money.currency),
            quantity=amount,
            account_chain_id=COINBASE_ACCOUNT_ID,
            is_fee=is_fee,
        )

    def _build_event(
        self,
        *,
        transactions: Iterable[CoinbaseTransaction],
        external_id: str,
        legs: Iterable[LedgerLeg],
    ) -> LedgerEvent | None:
        collapsed_legs = _collapse_legs(legs)
        if not collapsed_legs:
            return None

        timestamp = min(transaction.created_at for transaction in transactions).astimezone(timezone.utc)
        return LedgerEvent(
            timestamp=timestamp,
            event_origin=EventOrigin(location=EventLocation.COINBASE, external_id=external_id),
            ingestion=INGESTION,
            legs=collapsed_legs,
        )

    def _build_buy_event(self, transactions: list[CoinbaseTransaction]) -> LedgerEvent | None:
        if len(transactions) not in {1, 2}:
            raise ValueError(
                f"Unsupported Coinbase buy group size={len(transactions)} nested_id={transactions[0].buy.id if transactions[0].buy else 'missing'}"
            )

        buy = transactions[0].buy
        assert buy is not None

        positive_rows = [tx for tx in transactions if tx.amount.amount > 0]
        negative_rows = [tx for tx in transactions if tx.amount.amount < 0]

        if len(transactions) == 2 and (len(positive_rows) != 1 or len(negative_rows) != 1):
            raise ValueError(f"Unsupported Coinbase buy row signs nested_id={buy.id}")

        legs = [self._amount_leg(transaction.amount) for transaction in transactions]
        if len(transactions) == 1:
            quote = _positive_quote_money(buy.total, transactions[0].native_amount)
            legs.append(self._amount_leg(quote, quantity=-quote.amount))

        return self._build_event(transactions=transactions, external_id=buy.id, legs=legs)

    def _build_sell_event(self, transactions: list[CoinbaseTransaction]) -> LedgerEvent | None:
        if len(transactions) not in {1, 2}:
            raise ValueError(
                f"Unsupported Coinbase sell group size={len(transactions)} nested_id={transactions[0].sell.id if transactions[0].sell else 'missing'}"
            )

        sell = transactions[0].sell
        assert sell is not None

        positive_rows = [tx for tx in transactions if tx.amount.amount > 0]
        negative_rows = [tx for tx in transactions if tx.amount.amount < 0]

        if len(transactions) == 2 and (len(positive_rows) != 1 or len(negative_rows) != 1):
            raise ValueError(f"Unsupported Coinbase sell row signs nested_id={sell.id}")

        legs = [self._amount_leg(transaction.amount) for transaction in transactions]
        if len(transactions) == 1:
            quote = _positive_quote_money(sell.total, transactions[0].native_amount)
            legs.append(self._amount_leg(quote, quantity=quote.amount))

        return self._build_event(transactions=transactions, external_id=sell.id, legs=legs)

    def _build_trade_event(self, transactions: list[CoinbaseTransaction]) -> LedgerEvent | None:
        if len(transactions) != 2:
            raise ValueError(
                f"Unsupported Coinbase trade group size={len(transactions)} nested_id={transactions[0].trade.id if transactions[0].trade else 'missing'}"
            )

        trade = transactions[0].trade
        assert trade is not None

        positive_rows = [tx for tx in transactions if tx.amount.amount > 0]
        negative_rows = [tx for tx in transactions if tx.amount.amount < 0]
        if len(positive_rows) != 1 or len(negative_rows) != 1:
            raise ValueError(f"Unsupported Coinbase trade row signs nested_id={trade.id}")

        legs = [self._amount_leg(transaction.amount) for transaction in transactions]
        return self._build_event(transactions=transactions, external_id=trade.id, legs=legs)

    def _build_wrap_event(
        self,
        positive_row: CoinbaseTransaction,
        negative_row: CoinbaseTransaction,
    ) -> LedgerEvent | None:
        legs = [
            self._amount_leg(negative_row.amount),
            self._amount_leg(positive_row.amount),
        ]
        external_id = self._synthetic_pair_origin("wrap_asset", [positive_row, negative_row])
        return self._build_event(
            transactions=[positive_row, negative_row],
            external_id=external_id,
            legs=legs,
        )

    def _build_single_row_event(self, transaction: CoinbaseTransaction) -> LedgerEvent | None:
        legs = [self._amount_leg(transaction.amount)]

        if (
            transaction.type == "send"
            and transaction.amount.amount < 0
            and transaction.network is not None
            and transaction.network.transaction_fee is not None
            and transaction.network.transaction_fee.amount != 0
        ):
            fee = transaction.network.transaction_fee
            legs.append(self._amount_leg(fee, quantity=-fee.amount, is_fee=True))

        return self._build_event(
            transactions=[transaction],
            external_id=transaction.id,
            legs=legs,
        )
