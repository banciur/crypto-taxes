from typing import Annotated

from fastapi import APIRouter, Depends

from api.dependencies import get_wallet_balance_repository
from db.wallet_projection import WalletBalanceRepository
from domain.wallet_projection import WalletBalance

router = APIRouter()


@router.get("/wallet-balances", response_model=list[WalletBalance])
def get_wallet_balances(
    repo: Annotated[WalletBalanceRepository, Depends(get_wallet_balance_repository)],
) -> list[WalletBalance]:
    return repo.get()
