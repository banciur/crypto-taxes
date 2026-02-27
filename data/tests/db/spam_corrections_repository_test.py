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

    created = repo.mark_as_spam(origin, SpamCorrectionSource.MANUAL)

    active = repo.list()

    assert len(active) == 1
    (reloaded,) = active
    assert reloaded.id == created.id
    assert reloaded.event_origin == origin
    assert reloaded.source == SpamCorrectionSource.MANUAL
    assert reloaded.is_deleted is False


def test_mark_as_spam_same_origin_and_source_is_idempotent(tmp_path: Path) -> None:
    session = init_corrections_db(db_file=tmp_path / "corrections.db", reset=True)
    repo = SpamCorrectionRepository(session)
    origin = _origin(EventLocation.BASE, "0xdup")

    first = repo.mark_as_spam(origin, SpamCorrectionSource.MANUAL)
    second = repo.mark_as_spam(origin, SpamCorrectionSource.MANUAL)

    active = repo.list()
    assert len(active) == 1
    assert second.id == first.id
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

    first = repo.mark_as_spam(origin, SpamCorrectionSource.MANUAL)
    repo.remove_spam_mark(origin)

    restored = repo.mark_as_spam(origin, SpamCorrectionSource.MANUAL)
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


def test_remove_spam_mark_removes_all_sources_for_origin(tmp_path: Path) -> None:
    session = init_corrections_db(db_file=tmp_path / "corrections.db", reset=True)
    repo = SpamCorrectionRepository(session)
    origin = _origin(EventLocation.BASE, "0xall")

    manual = repo.mark_as_spam(origin, SpamCorrectionSource.MANUAL)
    auto = repo.mark_as_spam(origin, SpamCorrectionSource.AUTO_MORALIS)
    repo.remove_spam_mark(origin)
    restored_manual = repo.mark_as_spam(origin, SpamCorrectionSource.MANUAL)

    assert manual.id != auto.id
    assert repo.list() == [restored_manual]
    assert restored_manual.id == manual.id
