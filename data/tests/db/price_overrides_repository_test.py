from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.price_overrides import PriceOverrideOrm, PriceOverrideRepository
from domain.ledger import AssetId, EventLocation, EventOrigin
from domain.price_override import PriceOverrideDraft
from tests.constants import ETH, USDC


def _origin(external_id: str, *, location: EventLocation = EventLocation.ETHEREUM) -> EventOrigin:
    return EventOrigin(location=location, external_id=external_id)


def _draft(
    *,
    external_id: str = "0xaaa",
    location: EventLocation = EventLocation.ETHEREUM,
    asset_id: str = ETH,
    rate_eur: str = "1500",
    note: str | None = None,
) -> PriceOverrideDraft:
    return PriceOverrideDraft(
        event_origin=_origin(external_id, location=location),
        asset_id=AssetId(asset_id),
        rate_eur=Decimal(rate_eur),
        note=note,
    )


@pytest.fixture()
def repo(price_overrides_session: Session) -> PriceOverrideRepository:
    return PriceOverrideRepository(price_overrides_session)


def test_create_round_trips_all_fields(repo: PriceOverrideRepository) -> None:
    created = repo.create(_draft(external_id="0xaaa", asset_id="ETH", rate_eur="1234.56", note="OTC deal"))

    listed = repo.list()

    assert len(listed) == 1
    override = listed[0]
    assert override.id == created.id
    assert override.asset_id == ETH
    assert override.rate_eur == Decimal("1234.56")
    assert override.note == "OTC deal"
    assert override.event_origin == _origin("0xaaa")


def test_persists_internal_synthetic_origin(repo: PriceOverrideRepository) -> None:
    created = repo.create(_draft(external_id="correction-uuid", location=EventLocation.INTERNAL))

    assert repo.list()[0].event_origin == created.event_origin
    assert created.event_origin.location == EventLocation.INTERNAL


def test_multiple_overrides_may_share_an_event_origin(repo: PriceOverrideRepository) -> None:
    repo.create(_draft(external_id="0xshared", asset_id="ETH"))
    repo.create(_draft(external_id="0xshared", asset_id="USDC", rate_eur="1"))

    assert {override.asset_id for override in repo.list()} == {ETH, USDC}


def test_rejects_a_second_override_for_the_same_origin_and_asset(repo: PriceOverrideRepository) -> None:
    repo.create(_draft(external_id="0xshared", asset_id=ETH, rate_eur="1500"))

    with pytest.raises(IntegrityError):
        repo.create(_draft(external_id="0xshared", asset_id=ETH, rate_eur="1600"))


def test_rates_by_origin_groups_by_event_origin_then_asset(repo: PriceOverrideRepository) -> None:
    eth_rate, usdc_rate = Decimal("1500"), Decimal("1")
    priced, other = _origin("0xpriced"), _origin("0xother")
    repo.create(_draft(external_id=priced.external_id, asset_id=ETH, rate_eur=str(eth_rate)))
    repo.create(_draft(external_id=priced.external_id, asset_id=USDC, rate_eur=str(usdc_rate)))
    repo.create(_draft(external_id=other.external_id, asset_id=ETH, rate_eur=str(eth_rate)))

    assert repo.rates_by_origin() == {
        priced: {ETH: eth_rate, USDC: usdc_rate},
        other: {ETH: eth_rate},
    }


def test_delete_removes_override(
    price_overrides_session: Session,
    repo: PriceOverrideRepository,
) -> None:
    override = repo.create(_draft(external_id="0xaaa"))

    repo.delete(override.id)

    assert repo.list() == []
    assert price_overrides_session.get(PriceOverrideOrm, override.id) is None


def test_delete_unknown_id_is_a_noop(repo: PriceOverrideRepository) -> None:
    created = repo.create(_draft(external_id="0xaaa"))

    repo.delete(created.id)
    repo.delete(created.id)

    assert repo.list() == []
