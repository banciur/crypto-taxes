from typing import Annotated

from fastapi import APIRouter, Depends

from api.dependencies import get_wallet_projection_repository
from db.wallet_projection import WalletProjectionRepository
from domain.wallet_projection import WalletTrackingState

router = APIRouter()


@router.get("/wallet-projection", response_model=WalletTrackingState)
def get_wallet_projection(
    repo: Annotated[WalletProjectionRepository, Depends(get_wallet_projection_repository)],
) -> WalletTrackingState:
    state = repo.get()
    if state is not None:
        return state

    return WalletTrackingState.not_run()
