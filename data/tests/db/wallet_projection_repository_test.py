from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from accounts import KRAKEN_ACCOUNT_ID
from db.wallet_projection import WalletBalanceOrm, WalletBalanceRepository
from domain.wallet_projection import WalletBalance
from tests.constants import BASE_WALLET, BTC, ETH, EUR, LEDGER_WALLET


@pytest.fixture()
def repo(test_session: Session) -> WalletBalanceRepository:
    return WalletBalanceRepository(test_session)


def test_get_returns_empty_list_when_no_balances_are_persisted(repo: WalletBalanceRepository) -> None:
    assert repo.get() == []


def test_replace_persists_balances_in_deterministic_order(repo: WalletBalanceRepository) -> None:
    kraken_eur = Decimal("1000")
    ledger_btc = Decimal("0.25")
    base_eth = Decimal("1.5")
    balances = [
        WalletBalance(account_chain_id=LEDGER_WALLET, asset_id=BTC, balance=ledger_btc),
        WalletBalance(account_chain_id=KRAKEN_ACCOUNT_ID, asset_id=EUR, balance=kraken_eur),
        WalletBalance(account_chain_id=BASE_WALLET, asset_id=ETH, balance=base_eth),
    ]

    persisted = repo.replace(balances)
    reloaded = repo.get()

    assert persisted == balances
    assert reloaded == [
        WalletBalance(account_chain_id=BASE_WALLET, asset_id=ETH, balance=base_eth),
        WalletBalance(account_chain_id=LEDGER_WALLET, asset_id=BTC, balance=ledger_btc),
        WalletBalance(account_chain_id=KRAKEN_ACCOUNT_ID, asset_id=EUR, balance=kraken_eur),
    ]


def test_replace_fully_replaces_prior_balances(
    repo: WalletBalanceRepository,
    test_session: Session,
) -> None:
    repo.replace(
        [
            WalletBalance(account_chain_id=BASE_WALLET, asset_id=EUR, balance=Decimal("5.0")),
            WalletBalance(account_chain_id=KRAKEN_ACCOUNT_ID, asset_id=ETH, balance=Decimal("1.0")),
        ]
    )

    final_balance = Decimal("2.0")
    replacement = [WalletBalance(account_chain_id=LEDGER_WALLET, asset_id=BTC, balance=final_balance)]

    repo.replace(replacement)

    assert repo.get() == replacement
    balance_rows = test_session.execute(select(WalletBalanceOrm)).scalars().all()
    assert [(row.account_chain_id, row.asset_id, row.balance) for row in balance_rows] == [
        (LEDGER_WALLET, BTC, final_balance)
    ]
