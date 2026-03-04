from datetime import datetime
from typing import Annotated, Iterable

from fastapi import APIRouter, Depends, Response

from api.dependencies import (
    get_raw_events_repository,
    get_seed_events_repository,
    get_spam_correction_repository,
)
from db.corrections import SpamCorrectionRepository
from db.repositories import LedgerEventRepository, SeedEventRepository
from domain.correction import SeedEvent, Spam
from domain.ledger import EventLocation, EventOrigin


class ApiSpamCorrection(Spam):
    timestamp: datetime


def _event_origin_key(event_origin: EventOrigin) -> tuple[EventLocation, str]:
    return event_origin.location, event_origin.external_id


def _api_spam_corrections(
    records: list[Spam],
    raw_event_timestamps: Iterable[tuple[EventOrigin, datetime]],
) -> list[ApiSpamCorrection]:
    records_by_origin = {_event_origin_key(record.event_origin): record for record in records}
    matched_timestamps_by_origin: dict[tuple[EventLocation, str], list[datetime]] = {
        key: [] for key in records_by_origin
    }
    ordered_origins: list[tuple[EventLocation, str]] = []

    for event_origin, timestamp in raw_event_timestamps:
        origin_key = _event_origin_key(event_origin)
        matched_timestamps = matched_timestamps_by_origin[origin_key]
        if len(matched_timestamps) == 0:
            ordered_origins.append(origin_key)
        matched_timestamps.append(timestamp)

    for origin_key, record in records_by_origin.items():
        matched_timestamps = matched_timestamps_by_origin[origin_key]
        if len(matched_timestamps) != 1:
            raise RuntimeError(
                "Spam correction must match exactly one raw event: "
                f"{record.event_origin.location.value}/{record.event_origin.external_id}"
            )

    return [
        ApiSpamCorrection(
            id=records_by_origin[origin_key].id,
            event_origin=records_by_origin[origin_key].event_origin,
            timestamp=matched_timestamps_by_origin[origin_key][0],
        )
        for origin_key in ordered_origins
    ]


router = APIRouter()


@router.get("/seed-events")
def get_seed_events(sr: Annotated[SeedEventRepository, Depends(get_seed_events_repository)]) -> list[SeedEvent]:
    return sr.list()


@router.get("/spam-corrections")
def get_spam_corrections(
    repo: Annotated[SpamCorrectionRepository, Depends(get_spam_correction_repository)],
    raw_repo: Annotated[LedgerEventRepository, Depends(get_raw_events_repository)],
) -> list[ApiSpamCorrection]:
    records = repo.list()
    raw_event_timestamps = raw_repo.list_event_timestamps_for_origins(record.event_origin for record in records)
    return _api_spam_corrections(records, raw_event_timestamps)


@router.post("/spam-corrections", status_code=204)
def create_spam_correction(
    payload: EventOrigin,
    repo: Annotated[SpamCorrectionRepository, Depends(get_spam_correction_repository)],
) -> Response:
    repo.mark_as_spam(payload)
    return Response(status_code=204)


@router.delete("/spam-corrections", status_code=204)
def delete_spam_correction(
    payload: EventOrigin,
    repo: Annotated[SpamCorrectionRepository, Depends(get_spam_correction_repository)],
) -> Response:
    repo.remove_spam_mark(payload)
    return Response(status_code=204)
