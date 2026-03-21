from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from accounts import KRAKEN_ACCOUNT_ID
from db.ledger_corrections import (
    LedgerCorrectionLegOrm,
    LedgerCorrectionOrm,
    LedgerCorrectionRepository,
    LedgerCorrectionSourceOrm,
)
from domain.correction import LedgerCorrection
from domain.ledger import EventLocation, EventOrigin, LedgerLeg
from tests.constants import BTC, ETH, LEDGER_WALLET


def _replacement(timestamp: datetime, external_id: str) -> LedgerCorrection:
    return LedgerCorrection(
        timestamp=timestamp,
        sources=[EventOrigin(location=EventLocation.ETHEREUM, external_id=external_id)],
        legs=[
            LedgerLeg(asset_id=BTC, quantity=Decimal("-0.1"), account_chain_id=KRAKEN_ACCOUNT_ID),
            LedgerLeg(asset_id=BTC, quantity=Decimal("0.09995"), account_chain_id=LEDGER_WALLET),
            LedgerLeg(asset_id=ETH, quantity=Decimal("-0.001"), account_chain_id=KRAKEN_ACCOUNT_ID, is_fee=True),
        ],
    )


def _opening_balance(timestamp: datetime) -> LedgerCorrection:
    return LedgerCorrection(
        timestamp=timestamp,
        legs=[LedgerLeg(asset_id=BTC, quantity=Decimal("0.5"), account_chain_id=LEDGER_WALLET)],
        price_per_token=Decimal("1.23"),
    )


@pytest.fixture()
def repo(corrections_session: Session) -> LedgerCorrectionRepository:
    return LedgerCorrectionRepository(corrections_session)


def test_create_and_list_orders_by_timestamp_desc(repo: LedgerCorrectionRepository) -> None:
    earlier = _opening_balance(datetime(2024, 2, 3, 10, 30, tzinfo=timezone.utc))
    later = _replacement(datetime(2024, 2, 4, 10, 30, tzinfo=timezone.utc), "0xlate")

    repo.create(earlier)
    repo.create(later)

    listed = repo.list()

    assert [correction.id for correction in listed] == [later.id, earlier.id]


def test_delete_source_backed_soft_deletes_and_keeps_tombstone(
    corrections_session: Session,
    repo: LedgerCorrectionRepository,
) -> None:
    correction = _replacement(datetime(2024, 2, 3, 10, 30, tzinfo=timezone.utc), "0xabc")

    repo.create(correction)
    repo.delete(correction.id)

    assert repo.list() == []
    assert repo.has_source(correction.sources[0]) is False
    assert repo.has_source(correction.sources[0], include_deleted=True) is True

    row = corrections_session.get(LedgerCorrectionOrm, correction.id)
    assert row is not None
    assert row.is_deleted is True
    source_rows = corrections_session.execute(select(LedgerCorrectionSourceOrm)).scalars().all()
    assert len(source_rows) == 1
    assert source_rows[0].is_deleted is True


def test_delete_source_less_hard_deletes_without_tombstone(
    corrections_session: Session,
    repo: LedgerCorrectionRepository,
) -> None:
    correction = _opening_balance(datetime(2024, 2, 3, 10, 30, tzinfo=timezone.utc))

    repo.create(correction)
    repo.delete(correction.id)

    assert repo.list() == []
    assert corrections_session.get(LedgerCorrectionOrm, correction.id) is None
    assert corrections_session.execute(select(LedgerCorrectionLegOrm)).scalars().all() == []
    assert corrections_session.execute(select(LedgerCorrectionSourceOrm)).scalars().all() == []


def test_manual_create_can_reuse_source_after_tombstone(repo: LedgerCorrectionRepository) -> None:
    first = _replacement(datetime(2024, 2, 3, 10, 30, tzinfo=timezone.utc), "0xshared")
    second = _replacement(datetime(2024, 2, 4, 10, 30, tzinfo=timezone.utc), "0xshared")

    repo.create(first)
    repo.delete(first.id)
    repo.create(second)

    listed = repo.list()
    assert [correction.id for correction in listed] == [second.id]
    assert repo.has_source(second.sources[0], include_deleted=True) is True


def test_create_rejects_duplicate_active_source(repo: LedgerCorrectionRepository) -> None:
    first = _replacement(datetime(2024, 2, 3, 10, 30, tzinfo=timezone.utc), "0xshared")
    second = _replacement(datetime(2024, 2, 4, 10, 30, tzinfo=timezone.utc), "0xshared")

    repo.create(first)

    with pytest.raises(IntegrityError):
        repo.create(second)
