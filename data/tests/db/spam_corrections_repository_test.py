from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.corrections_spam import SpamCorrectionOrm, SpamCorrectionRepository, SpamCorrectionSource
from domain.ledger import EventLocation, EventOrigin


def _row(session: Session, origin: EventOrigin) -> SpamCorrectionOrm:
    stmt = select(SpamCorrectionOrm).where(
        SpamCorrectionOrm.origin_location == origin.location.value,
        SpamCorrectionOrm.origin_external_id == origin.external_id,
    )
    row = session.execute(stmt).scalar_one_or_none()
    assert row is not None
    return row


@pytest.fixture()
def repo(corrections_session: Session) -> SpamCorrectionRepository:
    return SpamCorrectionRepository(corrections_session)


def test_mark_as_spam_and_list(corrections_session: Session, repo: SpamCorrectionRepository) -> None:
    event_origin = EventOrigin(location=EventLocation.ARBITRUM, external_id="0xabc")

    repo.mark_as_spam(event_origin, SpamCorrectionSource.MANUAL)

    active = repo.list()

    assert len(active) == 1
    (reloaded,) = active
    assert reloaded.event_origin == event_origin
    assert _row(corrections_session, event_origin).source == SpamCorrectionSource.MANUAL.value


def test_mark_as_spam_same_origin_and_source_is_idempotent(repo: SpamCorrectionRepository) -> None:
    event_origin = EventOrigin(location=EventLocation.BASE, external_id="0xdup")

    repo.mark_as_spam(event_origin, SpamCorrectionSource.MANUAL)
    first = repo.list()[0]
    repo.mark_as_spam(event_origin, SpamCorrectionSource.MANUAL)

    active = repo.list()
    assert len(active) == 1
    assert active[0].id == first.id


def test_remove_spam_mark_hides_record_from_list(repo: SpamCorrectionRepository) -> None:
    event_origin = EventOrigin(location=EventLocation.ETHEREUM, external_id="0xspam")
    repo.mark_as_spam(event_origin, SpamCorrectionSource.MANUAL)

    repo.remove_spam_mark(event_origin)

    assert repo.list() == []


def test_mark_as_spam_after_remove_restores_same_row(repo: SpamCorrectionRepository) -> None:
    event_origin = EventOrigin(location=EventLocation.OPTIMISM, external_id="0xrestore")

    repo.mark_as_spam(event_origin, SpamCorrectionSource.MANUAL)
    first = repo.list()[0]
    repo.remove_spam_mark(event_origin)

    repo.mark_as_spam(event_origin, SpamCorrectionSource.MANUAL)
    restored = repo.list()[0]
    assert restored.id == first.id


def test_different_origins_are_stored_independently(repo: SpamCorrectionRepository) -> None:
    origin_a = EventOrigin(location=EventLocation.ARBITRUM, external_id="0xb")
    origin_b = EventOrigin(location=EventLocation.ARBITRUM, external_id="0xa")

    repo.mark_as_spam(origin_a, SpamCorrectionSource.MANUAL)
    repo.mark_as_spam(origin_b, SpamCorrectionSource.MANUAL)

    active = repo.list()
    assert [record.event_origin.external_id for record in active] == [origin_b.external_id, origin_a.external_id]


def test_mark_as_spam_same_origin_updates_source_and_reuses_row(
    corrections_session: Session,
    repo: SpamCorrectionRepository,
) -> None:
    event_origin = EventOrigin(location=EventLocation.BASE, external_id="0xall")

    repo.mark_as_spam(event_origin, SpamCorrectionSource.MANUAL)
    manual = repo.list()[0]
    repo.mark_as_spam(event_origin, SpamCorrectionSource.AUTO_MORALIS)
    auto = repo.list()[0]

    assert auto.id == manual.id
    assert repo.list() == [auto]
    assert _row(corrections_session, event_origin).source == SpamCorrectionSource.AUTO_MORALIS.value


def test_mark_as_spam_with_skip_if_exists_inserts_when_absent(
    corrections_session: Session,
    repo: SpamCorrectionRepository,
) -> None:
    event_origin = EventOrigin(location=EventLocation.KRAKEN, external_id="0xnew")

    repo.mark_as_spam(event_origin, SpamCorrectionSource.AUTO_MORALIS, skip_if_exists=True)

    active = repo.list()
    assert len(active) == 1
    assert active[0].event_origin == event_origin
    assert _row(corrections_session, event_origin).source == SpamCorrectionSource.AUTO_MORALIS.value


def test_mark_as_spam_with_skip_if_exists_leaves_existing_active_row_untouched(
    corrections_session: Session,
    repo: SpamCorrectionRepository,
) -> None:
    event_origin = EventOrigin(location=EventLocation.BASE, external_id="0xkeep")

    repo.mark_as_spam(event_origin, SpamCorrectionSource.MANUAL)
    first = repo.list()[0]

    repo.mark_as_spam(event_origin, SpamCorrectionSource.AUTO_MORALIS, skip_if_exists=True)

    active = repo.list()
    assert active == [first]
    assert _row(corrections_session, event_origin).source == SpamCorrectionSource.MANUAL.value


def test_mark_as_spam_with_skip_if_exists_does_not_revive_deleted_row(
    corrections_session: Session,
    repo: SpamCorrectionRepository,
) -> None:
    event_origin = EventOrigin(location=EventLocation.ETHEREUM, external_id="0xtombstone")

    repo.mark_as_spam(event_origin, SpamCorrectionSource.MANUAL)
    repo.remove_spam_mark(event_origin)

    repo.mark_as_spam(event_origin, SpamCorrectionSource.AUTO_MORALIS, skip_if_exists=True)

    assert repo.list() == []
    row = _row(corrections_session, event_origin)
    assert row.is_deleted is True
    assert row.source == SpamCorrectionSource.MANUAL.value
