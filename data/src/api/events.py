from typing import Annotated

from fastapi import APIRouter, Depends

from api.dependencies import (
    get_corrected_events_repository,
    get_raw_events_repository,
)
from db.repositories import CorrectedLedgerEventRepository, LedgerEventRepository
from domain.ledger import LedgerEvent

router = APIRouter()


@router.get("/raw-events")
def get_raw_events(rr: Annotated[LedgerEventRepository, Depends(get_raw_events_repository)]) -> list[LedgerEvent]:
    return rr.list()


@router.get("/corrected-events")
def get_corrected_events(
    cr: Annotated[CorrectedLedgerEventRepository, Depends(get_corrected_events_repository)],
) -> list[LedgerEvent]:
    return cr.list()
