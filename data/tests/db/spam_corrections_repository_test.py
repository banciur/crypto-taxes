from __future__ import annotations

from pathlib import Path

from db.corrections import SpamCorrectionRepository, init_corrections_db
from domain.correction import SpamCorrectionSource
from domain.ledger import EventLocation, EventOrigin


def _origin(location: EventLocation, external_id: str) -> EventOrigin:
    return EventOrigin(location=location, external_id=external_id)


def test_mark_as_spam_and_list(tmp_path: Path) -> None:
    session = init_corrections_db(db_file=tmp_path / "corrections.db", reset=True)
    repo = SpamCorrectionRepository(session)
    origin = _origin(EventLocation.ARBITRUM, "0xabc")

    repo.mark_as_spam(origin, SpamCorrectionSource.MANUAL)

    active = repo.list()

    assert len(active) == 1
    (reloaded,) = active
    assert reloaded.event_origin == origin
    assert reloaded.source == SpamCorrectionSource.MANUAL
    assert reloaded.is_deleted is False


def test_mark_as_spam_same_origin_and_source_is_idempotent(tmp_path: Path) -> None:
    session = init_corrections_db(db_file=tmp_path / "corrections.db", reset=True)
    repo = SpamCorrectionRepository(session)
    origin = _origin(EventLocation.BASE, "0xdup")

    repo.mark_as_spam(origin, SpamCorrectionSource.MANUAL)
    first = repo.list()[0]
    repo.mark_as_spam(origin, SpamCorrectionSource.MANUAL)

    active = repo.list()
    assert len(active) == 1
    assert active[0].id == first.id


def test_remove_spam_mark_hides_record_from_list(tmp_path: Path) -> None:
    session = init_corrections_db(db_file=tmp_path / "corrections.db", reset=True)
    repo = SpamCorrectionRepository(session)
    origin = _origin(EventLocation.ETHEREUM, "0xspam")
    repo.mark_as_spam(origin, SpamCorrectionSource.MANUAL)

    repo.remove_spam_mark(origin)

    assert repo.list() == []


def test_mark_as_spam_after_remove_restores_same_row(tmp_path: Path) -> None:
    session = init_corrections_db(db_file=tmp_path / "corrections.db", reset=True)
    repo = SpamCorrectionRepository(session)
    origin = _origin(EventLocation.OPTIMISM, "0xrestore")

    repo.mark_as_spam(origin, SpamCorrectionSource.MANUAL)
    first = repo.list()[0]
    repo.remove_spam_mark(origin)

    repo.mark_as_spam(origin, SpamCorrectionSource.MANUAL)
    restored = repo.list()[0]
    assert restored.id == first.id
    assert restored.is_deleted is False


def test_different_origins_are_stored_independently(tmp_path: Path) -> None:
    session = init_corrections_db(db_file=tmp_path / "corrections.db", reset=True)
    repo = SpamCorrectionRepository(session)
    origin_a = _origin(EventLocation.ARBITRUM, "0xb")
    origin_b = _origin(EventLocation.ARBITRUM, "0xa")

    repo.mark_as_spam(origin_a, SpamCorrectionSource.MANUAL)
    repo.mark_as_spam(origin_b, SpamCorrectionSource.MANUAL)

    active = repo.list()
    assert [record.event_origin.external_id for record in active] == [origin_b.external_id, origin_a.external_id]
    assert {record.source for record in active} == {SpamCorrectionSource.MANUAL}


def test_mark_as_spam_same_origin_updates_source_and_reuses_row(tmp_path: Path) -> None:
    session = init_corrections_db(db_file=tmp_path / "corrections.db", reset=True)
    repo = SpamCorrectionRepository(session)
    origin = _origin(EventLocation.BASE, "0xall")

    repo.mark_as_spam(origin, SpamCorrectionSource.MANUAL)
    manual = repo.list()[0]
    repo.mark_as_spam(origin, SpamCorrectionSource.AUTO_MORALIS)
    auto = repo.list()[0]

    assert auto.id == manual.id
    assert auto.source == SpamCorrectionSource.AUTO_MORALIS
    assert repo.list() == [auto]
