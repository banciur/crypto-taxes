from typing import Annotated

from fastapi import APIRouter, Depends

from api.dependencies import get_wallet_tracking_repository
from db.wallet_tracking import WalletTrackingRepository
from domain.wallet_tracking import WalletTrackingState

router = APIRouter()


@router.get("/wallet-tracking", response_model=WalletTrackingState)
def get_wallet_tracking(
    repo: Annotated[WalletTrackingRepository, Depends(get_wallet_tracking_repository)],
) -> WalletTrackingState:
    state = repo.get()
    if state is not None:
        return state

    return WalletTrackingState.not_run()
