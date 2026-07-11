from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.dependencies import get_price_override_repository, get_price_overrides_session
from db.price_overrides import PriceOverrideRepository
from domain.price_override import PriceOverride, PriceOverrideDraft, PriceOverrideId

router = APIRouter()


@router.get("/price-overrides", response_model=list[PriceOverride])
def get_price_overrides(
    override_repo: Annotated[PriceOverrideRepository, Depends(get_price_override_repository)],
) -> list[PriceOverride]:
    return override_repo.list()


@router.post(
    "/price-overrides",
    response_model=PriceOverride,
    status_code=status.HTTP_201_CREATED,
)
def create_price_override(
    payload: PriceOverrideDraft,
    override_repo: Annotated[PriceOverrideRepository, Depends(get_price_override_repository)],
    price_overrides_session: Annotated[Session, Depends(get_price_overrides_session)],
) -> PriceOverride:
    try:
        return override_repo.create(payload)
    except IntegrityError as error:
        price_overrides_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This asset already has a price override on this event",
        ) from error


@router.delete("/price-overrides/{override_id}", status_code=204)
def delete_price_override(
    override_id: UUID,
    override_repo: Annotated[PriceOverrideRepository, Depends(get_price_override_repository)],
) -> Response:
    override_repo.delete(PriceOverrideId(override_id))
    return Response(status_code=204)
