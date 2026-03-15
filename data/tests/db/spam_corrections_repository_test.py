from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.corrections_common import init_corrections_db
from db.corrections_spam import SpamCorrectionOrm, SpamCorrectionRepository, SpamCorrectionSource
from domain.ledger import EventLocation, EventOrigin


def _origin(location: EventLocation, external_id: str) -> EventOrigin:
    return EventOrigin(location=location, external_id=external_id)


def _row(session: Session, origin: EventOrigin) -> SpamCorrectionOrm:
    stmt = select(SpamCorrectionOrm).where(
        SpamCorrectionOrm.origin_location == origin.location.value,
        SpamCorrectionOrm.origin_external_id == origin.external_id,
    )
    row = session.execute(stmt).scalar_one_or_none()
    assert row is not None
    return row


def test_mark_as_spam_and_list(tmp_path: Path) -> None:
    session = init_corrections_db(db_path=tmp_path / "corrections.db", reset=True)
    repo = SpamCorrectionRepository(session)
    origin = _origin(EventLocation.ARBITRUM, "0xabc")

    repo.mark_as_spam(origin, SpamCorrectionSource.MANUAL)

    active = repo.list()

    assert len(active) == 1
    (reloaded,) = active
    assert reloaded.event_origin == origin
    assert _row(session, origin).source == SpamCorrectionSource.MANUAL.value


def test_mark_as_spam_same_origin_and_source_is_idempotent(tmp_path: Path) -> None:
    session = init_corrections_db(db_path=tmp_path / "corrections.db", reset=True)
    repo = SpamCorrectionRepository(session)
    origin = _origin(EventLocation.BASE, "0xdup")

    repo.mark_as_spam(origin, SpamCorrectionSource.MANUAL)
    first = repo.list()[0]
    repo.mark_as_spam(origin, SpamCorrectionSource.MANUAL)

    active = repo.list()
    assert len(active) == 1
    assert active[0].id == first.id


def test_remove_spam_mark_hides_record_from_list(tmp_path: Path) -> None:
    session = init_corrections_db(db_path=tmp_path / "corrections.db", reset=True)
    repo = SpamCorrectionRepository(session)
    origin = _origin(EventLocation.ETHEREUM, "0xspam")
    repo.mark_as_spam(origin, SpamCorrectionSource.MANUAL)

    repo.remove_spam_mark(origin)

    assert repo.list() == []


def test_mark_as_spam_after_remove_restores_same_row(tmp_path: Path) -> None:
    session = init_corrections_db(db_path=tmp_path / "corrections.db", reset=True)
    repo = SpamCorrectionRepository(session)
    origin = _origin(EventLocation.OPTIMISM, "0xrestore")

    repo.mark_as_spam(origin, SpamCorrectionSource.MANUAL)
    first = repo.list()[0]
    repo.remove_spam_mark(origin)

    repo.mark_as_spam(origin, SpamCorrectionSource.MANUAL)
    restored = repo.list()[0]
    assert restored.id == first.id


def test_different_origins_are_stored_independently(tmp_path: Path) -> None:
    session = init_corrections_db(db_path=tmp_path / "corrections.db", reset=True)
    repo = SpamCorrectionRepository(session)
    origin_a = _origin(EventLocation.ARBITRUM, "0xb")
    origin_b = _origin(EventLocation.ARBITRUM, "0xa")

    repo.mark_as_spam(origin_a, SpamCorrectionSource.MANUAL)
    repo.mark_as_spam(origin_b, SpamCorrectionSource.MANUAL)

    active = repo.list()
    assert [record.event_origin.external_id for record in active] == [origin_b.external_id, origin_a.external_id]


def test_mark_as_spam_same_origin_updates_source_and_reuses_row(tmp_path: Path) -> None:
    session = init_corrections_db(db_path=tmp_path / "corrections.db", reset=True)
    repo = SpamCorrectionRepository(session)
    origin = _origin(EventLocation.BASE, "0xall")

    repo.mark_as_spam(origin, SpamCorrectionSource.MANUAL)
    manual = repo.list()[0]
    repo.mark_as_spam(origin, SpamCorrectionSource.AUTO_MORALIS)
    auto = repo.list()[0]

    assert auto.id == manual.id
    assert repo.list() == [auto]
    assert _row(session, origin).source == SpamCorrectionSource.AUTO_MORALIS.value


def test_mark_as_spam_with_skip_if_exists_inserts_when_absent(tmp_path: Path) -> None:
    session = init_corrections_db(db_path=tmp_path / "corrections.db", reset=True)
    repo = SpamCorrectionRepository(session)
    origin = _origin(EventLocation.KRAKEN, "0xnew")

    repo.mark_as_spam(origin, SpamCorrectionSource.AUTO_MORALIS, skip_if_exists=True)

    active = repo.list()
    assert len(active) == 1
    assert active[0].event_origin == origin
    assert _row(session, origin).source == SpamCorrectionSource.AUTO_MORALIS.value


def test_mark_as_spam_with_skip_if_exists_leaves_existing_active_row_untouched(tmp_path: Path) -> None:
    session = init_corrections_db(db_path=tmp_path / "corrections.db", reset=True)
    repo = SpamCorrectionRepository(session)
    origin = _origin(EventLocation.BASE, "0xkeep")

    repo.mark_as_spam(origin, SpamCorrectionSource.MANUAL)
    first = repo.list()[0]

    repo.mark_as_spam(origin, SpamCorrectionSource.AUTO_MORALIS, skip_if_exists=True)

    active = repo.list()
    assert active == [first]
    assert _row(session, origin).source == SpamCorrectionSource.MANUAL.value


def test_mark_as_spam_with_skip_if_exists_does_not_revive_deleted_row(tmp_path: Path) -> None:
    session = init_corrections_db(db_path=tmp_path / "corrections.db", reset=True)
    repo = SpamCorrectionRepository(session)
    origin = _origin(EventLocation.ETHEREUM, "0xtombstone")

    repo.mark_as_spam(origin, SpamCorrectionSource.MANUAL)
    repo.remove_spam_mark(origin)

    repo.mark_as_spam(origin, SpamCorrectionSource.AUTO_MORALIS, skip_if_exists=True)

    assert repo.list() == []
    row = _row(session, origin)
    assert row.is_deleted is True
    assert row.source == SpamCorrectionSource.MANUAL.value
