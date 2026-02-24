from __future__ import annotations

from pathlib import Path

from db.corrections_store import SpamCorrectionRepository, init_corrections_db
from domain.correction import SpamCorrectionSource
from domain.ledger import EventLocation, EventOrigin


def _origin(location: EventLocation, external_id: str) -> EventOrigin:
    return EventOrigin(location=location, external_id=external_id)


def test_create_and_list_active_manual_spam_corrections(tmp_path: Path) -> None:
    session = init_corrections_db(db_file=tmp_path / "corrections.db", reset=True)
    repo = SpamCorrectionRepository(session)
    origin = _origin(EventLocation.ARBITRUM, "0xabc")

    created = repo.upsert_active(origin, SpamCorrectionSource.MANUAL)

    active = repo.list_active()

    assert len(active) == 1
    (reloaded,) = active
    assert reloaded.id == created.id
    assert reloaded.event_origin == origin
    assert reloaded.source == SpamCorrectionSource.MANUAL
    assert reloaded.deleted_at is None


def test_upsert_same_origin_and_source_is_idempotent(tmp_path: Path) -> None:
    session = init_corrections_db(db_file=tmp_path / "corrections.db", reset=True)
    repo = SpamCorrectionRepository(session)
    origin = _origin(EventLocation.BASE, "0xdup")

    first = repo.upsert_active(origin, SpamCorrectionSource.MANUAL)
    second = repo.upsert_active(origin, SpamCorrectionSource.MANUAL)

    active = repo.list_active()
    assert len(active) == 1
    assert second.id == first.id
    assert active[0].id == first.id


def test_soft_delete_hides_record_from_active_list(tmp_path: Path) -> None:
    session = init_corrections_db(db_file=tmp_path / "corrections.db", reset=True)
    repo = SpamCorrectionRepository(session)
    origin = _origin(EventLocation.ETHEREUM, "0xspam")
    repo.upsert_active(origin, SpamCorrectionSource.MANUAL)

    deleted = repo.soft_delete(origin, SpamCorrectionSource.MANUAL)

    stored = repo.get_by_origin_and_source(origin, SpamCorrectionSource.MANUAL)
    active = repo.list_active()
    assert deleted is True
    assert stored is not None
    assert stored.deleted_at is not None
    assert active == []


def test_recreate_after_delete_undeletes_same_row(tmp_path: Path) -> None:
    session = init_corrections_db(db_file=tmp_path / "corrections.db", reset=True)
    repo = SpamCorrectionRepository(session)
    origin = _origin(EventLocation.OPTIMISM, "0xrestore")

    first = repo.upsert_active(origin, SpamCorrectionSource.MANUAL)
    repo.soft_delete(origin, SpamCorrectionSource.MANUAL)

    restored = repo.upsert_active(origin, SpamCorrectionSource.MANUAL)
    stored = repo.get_by_origin_and_source(origin, SpamCorrectionSource.MANUAL)
    assert stored is not None
    assert restored.id == first.id
    assert stored.id == first.id
    assert stored.deleted_at is None


def test_different_origins_are_stored_independently(tmp_path: Path) -> None:
    session = init_corrections_db(db_file=tmp_path / "corrections.db", reset=True)
    repo = SpamCorrectionRepository(session)
    origin_a = _origin(EventLocation.ARBITRUM, "0xb")
    origin_b = _origin(EventLocation.ARBITRUM, "0xa")

    repo.upsert_active(origin_a, SpamCorrectionSource.MANUAL)
    repo.upsert_active(origin_b, SpamCorrectionSource.MANUAL)

    active = repo.list_active()
    assert [record.event_origin.external_id for record in active] == [origin_b.external_id, origin_a.external_id]
    assert {record.source for record in active} == {SpamCorrectionSource.MANUAL}
