from __future__ import annotations

from decimal import Decimal

from domain.ledger import AccountChainId, AssetId, LedgerLeg
from tests.constants import BASE_WALLET, ETH


def make_leg(
    *,
    quantity: Decimal,
    asset_id: AssetId = ETH,
    account_chain_id: AccountChainId = BASE_WALLET,
    is_fee: bool = False,
) -> LedgerLeg:
    return LedgerLeg(
        asset_id=asset_id,
        quantity=quantity,
        account_chain_id=account_chain_id,
        is_fee=is_fee,
    )
