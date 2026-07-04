from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends

from api.dependencies import get_acquisition_disposal_projection_repository
from db.acquisition_disposal import AcquisitionDisposalProjectionRepository
from domain.acquisition_disposal.models import AcquisitionLot, DisposalLink
from domain.ledger import AccountChainId, AssetId, EventOrigin
from pydantic_base import StrictBaseModel

router = APIRouter()


class AcquisitionDisposalBaseItem(StrictBaseModel):
    id: str
    timestamp: datetime
    event_origin: EventOrigin
    account_chain_id: AccountChainId
    asset_id: AssetId
    is_fee: bool


class AcquisitionDisplayItem(AcquisitionDisposalBaseItem):
    kind: Literal["ACQUISITION"] = "ACQUISITION"
    quantity_acquired: Decimal
    cost_per_unit: Decimal


class DisposalDisplayItem(AcquisitionDisposalBaseItem):
    kind: Literal["DISPOSAL"] = "DISPOSAL"
    acquisition_id: str
    acquisition_timestamp: datetime
    acquisition_event_origin: EventOrigin
    quantity_used: Decimal
    proceeds_total: Decimal
    cost_basis_total: Decimal


AcquisitionDisposalDisplayItem = AcquisitionDisplayItem | DisposalDisplayItem


@router.get("/acquisition-disposal", response_model=list[AcquisitionDisposalDisplayItem])
def get_acquisition_disposal_projection(
    repo: Annotated[
        AcquisitionDisposalProjectionRepository,
        Depends(get_acquisition_disposal_projection_repository),
    ],
) -> list[AcquisitionDisposalDisplayItem]:
    projection = repo.get()
    lots_by_id = {lot.id: lot for lot in projection.acquisition_lots}
    items: list[AcquisitionDisposalDisplayItem] = [_acquisition_item(lot) for lot in projection.acquisition_lots]

    items.extend(
        _disposal_item(link=link, acquisition_lot=lots_by_id[link.lot_id]) for link in projection.disposal_links
    )
    return sorted(items, key=lambda item: (item.timestamp, item.kind, item.id))


def _acquisition_item(lot: AcquisitionLot) -> AcquisitionDisplayItem:
    return AcquisitionDisplayItem(
        id=str(lot.id),
        timestamp=lot.timestamp,
        event_origin=lot.event_origin,
        account_chain_id=lot.account_chain_id,
        asset_id=lot.asset_id,
        is_fee=lot.is_fee,
        quantity_acquired=lot.quantity_acquired,
        cost_per_unit=lot.cost_per_unit,
    )


def _disposal_item(*, link: DisposalLink, acquisition_lot: AcquisitionLot) -> DisposalDisplayItem:
    cost_basis_total = link.quantity_used * acquisition_lot.cost_per_unit

    return DisposalDisplayItem(
        id=str(link.id),
        timestamp=link.timestamp,
        event_origin=link.event_origin,
        account_chain_id=link.account_chain_id,
        asset_id=link.asset_id,
        is_fee=link.is_fee,
        acquisition_id=str(acquisition_lot.id),
        acquisition_timestamp=acquisition_lot.timestamp,
        acquisition_event_origin=acquisition_lot.event_origin,
        quantity_used=link.quantity_used,
        proceeds_total=link.proceeds_total,
        cost_basis_total=cost_basis_total,
    )
