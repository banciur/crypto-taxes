from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.price_overrides import PriceOverrideOrm, PriceOverrideRepository, PriceOverrideSourceOrm
from domain.ledger import AssetId, EventLocation, EventOrigin
from domain.price_override import PriceOverrideDraft
from tests.constants import ETH, USDC


def _origin(external_id: str, *, location: EventLocation = EventLocation.ETHEREUM) -> EventOrigin:
    return EventOrigin(location=location, external_id=external_id)


def _draft(
    *,
    external_ids: tuple[str, ...],
    asset_id: str = ETH,
    rate_eur: str = "1500",
    note: str | None = None,
) -> PriceOverrideDraft:
    return PriceOverrideDraft(
        sources=frozenset(_origin(external_id) for external_id in external_ids),
        asset_id=AssetId(asset_id),
        rate_eur=Decimal(rate_eur),
        note=note,
    )


@pytest.fixture()
def repo(price_overrides_session: Session) -> PriceOverrideRepository:
    return PriceOverrideRepository(price_overrides_session)


def test_create_round_trips_all_fields(repo: PriceOverrideRepository) -> None:
    created = repo.create(_draft(external_ids=("0xaaa", "0xbbb"), asset_id="eth", rate_eur="1234.56", note="OTC deal"))

    listed = repo.list()

    assert len(listed) == 1
    override = listed[0]
    assert override.id == created.id
    assert override.asset_id == ETH
    assert override.rate_eur == Decimal("1234.56")
    assert override.note == "OTC deal"
    assert {source.external_id for source in override.sources} == {"0xaaa", "0xbbb"}


def test_multiple_overrides_may_share_a_source_origin(repo: PriceOverrideRepository) -> None:
    repo.create(_draft(external_ids=("0xshared",), asset_id="ETH"))
    repo.create(_draft(external_ids=("0xshared",), asset_id="USDC", rate_eur="1"))

    assert {override.asset_id for override in repo.list()} == {ETH, USDC}


def test_delete_removes_override_and_its_sources(
    price_overrides_session: Session,
    repo: PriceOverrideRepository,
) -> None:
    override = repo.create(_draft(external_ids=("0xaaa", "0xbbb")))

    repo.delete(override.id)

    assert repo.list() == []
    assert price_overrides_session.get(PriceOverrideOrm, override.id) is None
    assert price_overrides_session.execute(select(PriceOverrideSourceOrm)).scalars().all() == []


def test_delete_unknown_id_is_a_noop(repo: PriceOverrideRepository) -> None:
    created = repo.create(_draft(external_ids=("0xaaa",)))

    repo.delete(created.id)
    repo.delete(created.id)

    assert repo.list() == []
