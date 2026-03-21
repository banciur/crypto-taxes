from datetime import datetime
from decimal import Decimal
from typing import Annotated, Iterable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import Field, ValidationError
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
from domain.correction import CorrectionId, LedgerCorrection
from domain.ledger import EventLocation, EventOrigin, LedgerLeg
from pydantic_base import StrictBaseModel


class CreateLedgerCorrectionPayload(StrictBaseModel):
    timestamp: datetime | None = None
    sources: list[EventOrigin] = Field(default_factory=list)
    legs: list[LedgerLeg] = Field(default_factory=list)
    price_per_token: Decimal | None = None
    note: str | None = None


def _event_origin_key(event_origin: EventOrigin) -> tuple[EventLocation, str]:
    return event_origin.location, event_origin.external_id


def _source_timestamp_map(
    raw_event_timestamps: Iterable[tuple[EventOrigin, datetime]],
) -> dict[tuple[EventLocation, str], list[datetime]]:
    matched_timestamps_by_origin: dict[tuple[EventLocation, str], list[datetime]] = {}
    for event_origin, timestamp in raw_event_timestamps:
        matched_timestamps_by_origin.setdefault(_event_origin_key(event_origin), []).append(timestamp)
    return matched_timestamps_by_origin


def _resolve_timestamp(
    *,
    payload: CreateLedgerCorrectionPayload,
    source_timestamps_by_origin: dict[tuple[EventLocation, str], list[datetime]],
) -> datetime:
    if payload.timestamp is not None:
        return payload.timestamp

    if len(payload.sources) == 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="timestamp is required")

    matched_source_timestamps: list[datetime] = []
    invalid_sources: list[tuple[EventLocation, str]] = []
    for source in payload.sources:
        matched = source_timestamps_by_origin.get(_event_origin_key(source), [])
        if len(matched) != 1:
            invalid_sources.append(_event_origin_key(source))
            continue
        matched_source_timestamps.append(matched[0])

    if invalid_sources:
        formatted_origins = ", ".join(
            f"{location.value}/{external_id}" for location, external_id in sorted(invalid_sources)
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Correction source must match exactly one raw event: {formatted_origins}",
        )

    return max(matched_source_timestamps)


def _build_correction(
    *,
    payload: CreateLedgerCorrectionPayload,
    raw_repo: LedgerEventRepository,
) -> LedgerCorrection:
    source_timestamps_by_origin = _source_timestamp_map(raw_repo.list_event_timestamps_for_origins(payload.sources))
    timestamp = _resolve_timestamp(payload=payload, source_timestamps_by_origin=source_timestamps_by_origin)
    try:
        return LedgerCorrection(
            timestamp=timestamp,
            sources=frozenset(payload.sources),
            legs=frozenset(payload.legs),
            price_per_token=payload.price_per_token,
            note=payload.note,
        )
    except ValidationError as error:
        detail = error.errors()[0]["msg"] if error.errors() else "Invalid correction payload"
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail) from error


router = APIRouter()


@router.get("/corrections")
def get_corrections(
    repo: Annotated[LedgerCorrectionRepository, Depends(get_correction_repository)],
) -> list[LedgerCorrection]:
    return repo.list()


@router.post(
    "/corrections",
    response_model=LedgerCorrection,
    status_code=status.HTTP_201_CREATED,
)
def create_correction(
    payload: CreateLedgerCorrectionPayload,
    repo: Annotated[LedgerCorrectionRepository, Depends(get_correction_repository)],
    raw_repo: Annotated[LedgerEventRepository, Depends(get_raw_events_repository)],
    corrections_session: Annotated[Session, Depends(get_corrections_session)],
) -> LedgerCorrection:
    correction = _build_correction(payload=payload, raw_repo=raw_repo)

    try:
        validate_ingestion_corrections(
            raw_events=raw_repo.list(),
            corrections=[*repo.list(), correction],
        )
    except CorrectionValidationError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    try:
        return repo.create(correction)
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
