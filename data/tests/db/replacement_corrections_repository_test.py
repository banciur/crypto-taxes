from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from accounts import KRAKEN_ACCOUNT_ID
from db.corrections_replacement import (
    ReplacementCorrectionLegOrm,
    ReplacementCorrectionOrm,
    ReplacementCorrectionRepository,
    ReplacementCorrectionSourceOrm,
)
from domain.correction import Replacement
from domain.ledger import EventLocation, EventOrigin, LedgerLeg
from tests.constants import BTC, ETH, LEDGER_WALLET


def _replacement(
    *,
    timestamp: datetime,
    source_external_ids: tuple[str, ...],
) -> Replacement:
    return Replacement(
        timestamp=timestamp,
        sources=[
            EventOrigin(location=EventLocation.ETHEREUM, external_id=source_external_ids[0]),
            *[
                EventOrigin(location=EventLocation.COINBASE, external_id=external_id)
                for external_id in source_external_ids[1:]
            ],
        ],
        legs=[
            LedgerLeg(
                asset_id=BTC,
                quantity=Decimal("-0.1"),
                account_chain_id=KRAKEN_ACCOUNT_ID,
            ),
            LedgerLeg(
                asset_id=BTC,
                quantity=Decimal("0.09995"),
                account_chain_id=LEDGER_WALLET,
            ),
            LedgerLeg(
                asset_id=ETH,
                quantity=Decimal("-0.001"),
                account_chain_id=KRAKEN_ACCOUNT_ID,
                is_fee=True,
            ),
        ],
    )


@pytest.fixture()
def repo(corrections_session: Session) -> ReplacementCorrectionRepository:
    return ReplacementCorrectionRepository(corrections_session)


def test_create_and_list_replacement(
    corrections_session: Session,
    repo: ReplacementCorrectionRepository,
) -> None:
    replacement = _replacement(
        timestamp=datetime(2024, 2, 3, 10, 30, tzinfo=timezone.utc),
        source_external_ids=("0xabc", "cb-123"),
    )

    saved = repo.create(replacement)
    listed = repo.list()

    assert saved == replacement
    assert len(listed) == 1
    reloaded = listed[0]
    assert reloaded.id == replacement.id
    assert reloaded.timestamp == replacement.timestamp
    assert {source.model_dump_json() for source in reloaded.sources} == {
        source.model_dump_json() for source in replacement.sources
    }
    assert {leg.id for leg in reloaded.legs} == {leg.id for leg in replacement.legs}
    reloaded_legs_by_id = {leg.id: leg for leg in reloaded.legs}
    for leg in replacement.legs:
        assert reloaded_legs_by_id[leg.id] == leg


def test_list_replacements_orders_by_timestamp(repo: ReplacementCorrectionRepository) -> None:
    later = _replacement(
        timestamp=datetime(2024, 2, 4, 10, 30, tzinfo=timezone.utc),
        source_external_ids=("0xlater",),
    )
    earlier = _replacement(
        timestamp=datetime(2024, 2, 3, 10, 30, tzinfo=timezone.utc),
        source_external_ids=("0xearlier",),
    )

    repo.create(later)
    repo.create(earlier)

    listed = repo.list()

    assert [replacement.id for replacement in listed] == [earlier.id, later.id]


def test_delete_replacement_cascades_to_legs_and_sources(
    corrections_session: Session,
    repo: ReplacementCorrectionRepository,
) -> None:
    replacement = _replacement(
        timestamp=datetime(2024, 2, 3, 10, 30, tzinfo=timezone.utc),
        source_external_ids=("0xabc", "cb-123"),
    )
    repo.create(replacement)

    repo.delete(replacement.id)

    assert corrections_session.get(ReplacementCorrectionOrm, replacement.id) is None
    assert repo.list() == []
    assert corrections_session.execute(select(ReplacementCorrectionLegOrm)).scalars().all() == []
    assert corrections_session.execute(select(ReplacementCorrectionSourceOrm)).scalars().all() == []


def test_create_replacement_rejects_duplicate_source_origin(repo: ReplacementCorrectionRepository) -> None:
    first = _replacement(
        timestamp=datetime(2024, 2, 3, 10, 30, tzinfo=timezone.utc),
        source_external_ids=("0xshared",),
    )
    second = _replacement(
        timestamp=datetime(2024, 2, 3, 10, 31, tzinfo=timezone.utc),
        source_external_ids=("0xshared",),
    )
    repo.create(first)

    with pytest.raises(IntegrityError):
        repo.create(second)
