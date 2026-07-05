from collections import defaultdict
from collections.abc import Iterable, Mapping, MutableMapping
from decimal import Decimal

from errors import CryptoTaxesError
from pydantic_base import StrictBaseModel

from .ledger import AccountChainId, AssetId, EventOrigin, LedgerEvent

BalanceKey = tuple[AccountChainId, AssetId]
BalanceMap = Mapping[BalanceKey, Decimal]
ZERO = Decimal(0)


class WalletBalance(StrictBaseModel):
    account_chain_id: AccountChainId
    asset_id: AssetId
    balance: Decimal


class WalletBalanceIssue(StrictBaseModel):
    account_chain_id: AccountChainId
    asset_id: AssetId
    attempted_delta: Decimal
    available_balance: Decimal
    missing_balance: Decimal


class WalletProjectionError(CryptoTaxesError):
    def __init__(self, *, event: EventOrigin, issues: list[WalletBalanceIssue]) -> None:
        self.event = event
        self.issues = issues
        detail = "; ".join(
            f"{issue.account_chain_id}/{issue.asset_id} attempted={issue.attempted_delta} "
            f"available={issue.available_balance} missing={issue.missing_balance}"
            for issue in issues
        )
        super().__init__(
            f"Wallet balance would go negative at event {event.location.value}/{event.external_id}: {detail}"
        )


class WalletProjector:
    def __init__(self) -> None:
        self._balances: MutableMapping[BalanceKey, Decimal] = {}

    @property
    def balances(self) -> list[WalletBalance]:
        return [
            WalletBalance(account_chain_id=account_chain_id, asset_id=asset_id, balance=balance)
            for (account_chain_id, asset_id), balance in sorted(self._balances.items())
        ]

    def project(self, events: Iterable[LedgerEvent]) -> list[WalletBalance]:
        for event in events:
            deltas = self._net_event_deltas(event)
            if issues := self._validate_event(deltas, self._balances):
                raise WalletProjectionError(event=event.event_origin, issues=issues)

            for key, delta in deltas.items():
                next_balance = self._balances.get(key, ZERO) + delta
                if next_balance == ZERO:
                    self._balances.pop(key, None)
                    continue
                self._balances[key] = next_balance

        return self.balances

    @staticmethod
    def _net_event_deltas(event: LedgerEvent) -> BalanceMap:
        deltas: defaultdict[BalanceKey, Decimal] = defaultdict(Decimal)
        for leg in event.legs:
            deltas[(leg.account_chain_id, leg.asset_id)] += leg.quantity

        return {key: delta for key, delta in deltas.items() if delta != ZERO}

    @staticmethod
    def _validate_event(
        deltas: BalanceMap,
        balances: BalanceMap,
    ) -> list[WalletBalanceIssue]:
        issues: list[WalletBalanceIssue] = []

        for (account_chain_id, asset_id), attempted_delta in sorted(deltas.items()):
            if attempted_delta >= ZERO:
                continue

            available_balance = balances.get((account_chain_id, asset_id), ZERO)
            new_balance = available_balance + attempted_delta
            if new_balance >= ZERO:
                continue

            issues.append(
                WalletBalanceIssue(
                    account_chain_id=account_chain_id,
                    asset_id=asset_id,
                    attempted_delta=attempted_delta,
                    available_balance=available_balance,
                    missing_balance=-new_balance,
                )
            )

        return issues
