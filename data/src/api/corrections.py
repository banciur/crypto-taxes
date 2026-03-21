from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.dependencies import (
    get_correction_repository,
    get_corrections_session,
    get_raw_events_repository,
)
from corrections.validation import CorrectionValidationError, validate_ingestion_corrections
from db.ledger_corrections import LedgerCorrectionRepository
from db.repositories import LedgerEventRepository
from domain.correction import CorrectionId, LedgerCorrection, LedgerCorrectionDraft

router = APIRouter()


@router.get(
    "/corrections",
    response_model=list[LedgerCorrection],
    response_model_exclude_none=True,
)
def get_corrections(
    repo: Annotated[LedgerCorrectionRepository, Depends(get_correction_repository)],
) -> list[LedgerCorrection]:
    return repo.list()


@router.post(
    "/corrections",
    response_model=LedgerCorrection,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def create_correction(
    payload: LedgerCorrectionDraft,
    corrected_repo: Annotated[LedgerCorrectionRepository, Depends(get_correction_repository)],
    raw_repo: Annotated[LedgerEventRepository, Depends(get_raw_events_repository)],
    corrections_session: Annotated[Session, Depends(get_corrections_session)],
) -> LedgerCorrection:
    try:
        validate_ingestion_corrections(
            raw_events=raw_repo.list(),
            corrections=[*corrected_repo.list(), payload],
        )
    except CorrectionValidationError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    try:
        return corrected_repo.create(payload)
    except IntegrityError as error:
        corrections_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Correction source is already consumed by another active correction",
        ) from error


@router.delete("/corrections/{correction_id}", status_code=204)
def delete_correction(
    correction_id: UUID,
    repo: Annotated[LedgerCorrectionRepository, Depends(get_correction_repository)],
) -> Response:
    repo.delete(CorrectionId(correction_id))
    return Response(status_code=204)
