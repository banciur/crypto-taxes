# TODO: Tests for LedgerCorrectionRepository were written quickly and do not cover most of the cases.
#  Please review and improve this file when making changes.

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from accounts import KRAKEN_ACCOUNT_ID
from db.ledger_corrections import (
    LedgerCorrectionAutoSuppressionOrm,
    LedgerCorrectionLegOrm,
    LedgerCorrectionOrm,
    LedgerCorrectionRepository,
    LedgerCorrectionSourceOrm,
)
from domain.correction import LedgerCorrectionDraft
from domain.ledger import EventLocation, EventOrigin, LedgerLeg
from tests.constants import BTC, ETH, LEDGER_WALLET


def _replacement(timestamp: datetime, external_id: str) -> LedgerCorrectionDraft:
    return LedgerCorrectionDraft(
        timestamp=timestamp,
        sources=frozenset([EventOrigin(location=EventLocation.ETHEREUM, external_id=external_id)]),
        legs=frozenset(
            [
                LedgerLeg(asset_id=BTC, quantity=Decimal("-0.1"), account_chain_id=KRAKEN_ACCOUNT_ID),
                LedgerLeg(asset_id=BTC, quantity=Decimal("0.09995"), account_chain_id=LEDGER_WALLET),
                LedgerLeg(
                    asset_id=ETH,
                    quantity=Decimal("-0.001"),
                    account_chain_id=KRAKEN_ACCOUNT_ID,
                    is_fee=True,
                ),
            ]
        ),
    )


def _opening_balance(timestamp: datetime) -> LedgerCorrectionDraft:
    return LedgerCorrectionDraft(
        timestamp=timestamp,
        legs=frozenset([LedgerLeg(asset_id=BTC, quantity=Decimal("0.5"), account_chain_id=LEDGER_WALLET)]),
        price_per_token=Decimal("1.23"),
    )


@pytest.fixture()
def repo(corrections_session: Session) -> LedgerCorrectionRepository:
    return LedgerCorrectionRepository(corrections_session)


def test_create_and_list_orders_by_timestamp_desc(repo: LedgerCorrectionRepository) -> None:
    earlier = repo.create(_opening_balance(datetime(2024, 2, 3, 10, 30, tzinfo=timezone.utc)))
    later = repo.create(_replacement(datetime(2024, 2, 4, 10, 30, tzinfo=timezone.utc), "0xlate"))

    listed = repo.list()

    assert [correction.id for correction in listed] == [later.id, earlier.id]


def test_delete_source_backed_hard_deletes_and_keeps_auto_suppression(
    corrections_session: Session,
    repo: LedgerCorrectionRepository,
) -> None:
    correction = repo.create(_replacement(datetime(2024, 2, 3, 10, 30, tzinfo=timezone.utc), "0xabc"))
    repo.delete(correction.id)

    assert repo.list() == []
    source = next(iter(correction.sources))
    assert repo.has_active_source(source) is False
    assert repo.is_auto_suppressed(source) is True

    assert corrections_session.get(LedgerCorrectionOrm, correction.id) is None
    assert corrections_session.execute(select(LedgerCorrectionSourceOrm)).scalars().all() == []
    suppression_rows = corrections_session.execute(select(LedgerCorrectionAutoSuppressionOrm)).scalars().all()
    assert len(suppression_rows) == 1
    assert suppression_rows[0].origin_location == source.location.value
    assert suppression_rows[0].origin_external_id == source.external_id


def test_delete_source_less_hard_deletes_without_auto_suppression(
    corrections_session: Session,
    repo: LedgerCorrectionRepository,
) -> None:
    correction = repo.create(_opening_balance(datetime(2024, 2, 3, 10, 30, tzinfo=timezone.utc)))
    repo.delete(correction.id)

    assert repo.list() == []
    assert corrections_session.get(LedgerCorrectionOrm, correction.id) is None
    assert corrections_session.execute(select(LedgerCorrectionLegOrm)).scalars().all() == []
    assert corrections_session.execute(select(LedgerCorrectionSourceOrm)).scalars().all() == []
    assert corrections_session.execute(select(LedgerCorrectionAutoSuppressionOrm)).scalars().all() == []


def test_manual_create_reuses_source_after_delete_despite_auto_suppression(
    corrections_session: Session,
    repo: LedgerCorrectionRepository,
) -> None:
    first = repo.create(_replacement(datetime(2024, 2, 3, 10, 30, tzinfo=timezone.utc), "0xshared"))
    second = _replacement(datetime(2024, 2, 4, 10, 30, tzinfo=timezone.utc), "0xshared")

    repo.delete(first.id)
    recreated = repo.create(second)

    assert next(iter(recreated.sources)).external_id == "0xshared"
    suppression_rows = corrections_session.execute(select(LedgerCorrectionAutoSuppressionOrm)).scalars().all()
    assert len(suppression_rows) == 1


def test_create_rejects_duplicate_active_source(repo: LedgerCorrectionRepository) -> None:
    first = _replacement(datetime(2024, 2, 3, 10, 30, tzinfo=timezone.utc), "0xshared")
    second = _replacement(datetime(2024, 2, 4, 10, 30, tzinfo=timezone.utc), "0xshared")

    repo.create(first)

    with pytest.raises(IntegrityError):
        repo.create(second)
