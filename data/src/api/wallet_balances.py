from typing import Annotated

from fastapi import APIRouter, Depends

from api.dependencies import get_wallet_projection_repository
from db.wallet_projection import WalletProjectionRepository
from domain.wallet_projection import WalletBalance

router = APIRouter()


@router.get("/wallet-balances", response_model=list[WalletBalance])
def get_wallet_balances(
    repo: Annotated[WalletProjectionRepository, Depends(get_wallet_projection_repository)],
) -> list[WalletBalance]:
    return repo.get().balances
