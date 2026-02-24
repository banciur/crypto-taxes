from __future__ import annotations

from pathlib import Path

from db.corrections_store import SpamCorrectionRepository, init_corrections_db
from domain.correction import Spam, SpamCorrectionSource
from domain.ledger import EventLocation, EventOrigin
from services.spam_correction_service import SpamCorrectionService


def _origin(location: EventLocation, external_id: str) -> EventOrigin:
    return EventOrigin(location=location, external_id=external_id)


def _service(tmp_path: Path) -> SpamCorrectionService:
    session = init_corrections_db(db_file=tmp_path / "corrections.db", reset=True)
    return SpamCorrectionService(SpamCorrectionRepository(session))


def test_create_manual_creates_active_record(tmp_path: Path) -> None:
    service = _service(tmp_path)
    origin = _origin(EventLocation.BASE, "0xmanual")

    created = service.create_manual(origin)

    assert created.event_origin == origin
    assert created.source == SpamCorrectionSource.MANUAL
    assert created.deleted_at is None
    assert service.list_active_manual() == [created]


def test_create_manual_undeletes_soft_deleted_record(tmp_path: Path) -> None:
    service = _service(tmp_path)
    origin = _origin(EventLocation.ARBITRUM, "0xrestore")

    first = service.create_manual(origin)
    service.delete_manual(origin)
    restored = service.create_manual(origin)

    active = service.list_active_manual()
    assert len(active) == 1
    assert restored.id == first.id
    assert active[0].id == first.id


def test_delete_manual_is_idempotent(tmp_path: Path) -> None:
    service = _service(tmp_path)
    origin = _origin(EventLocation.ETHEREUM, "0xdelete")
    service.create_manual(origin)

    service.delete_manual(origin)
    service.delete_manual(origin)

    assert service.list_active_manual() == []


def test_list_active_markers_returns_spam_markers_for_all_active_sources(tmp_path: Path) -> None:
    session = init_corrections_db(db_file=tmp_path / "corrections.db", reset=True)
    repo = SpamCorrectionRepository(session)
    service = SpamCorrectionService(repo)
    manual_origin = _origin(EventLocation.BASE, "0xmanual")
    auto_origin = _origin(EventLocation.OPTIMISM, "0xauto")
    deleted_origin = _origin(EventLocation.ARBITRUM, "0xdeleted")

    manual_record = repo.upsert_active(manual_origin, SpamCorrectionSource.MANUAL)
    auto_record = repo.upsert_active(auto_origin, SpamCorrectionSource.AUTO_MORALIS)
    repo.upsert_active(deleted_origin, SpamCorrectionSource.MANUAL)
    repo.soft_delete(deleted_origin, SpamCorrectionSource.MANUAL)

    markers = service.list_active_markers()

    assert all(isinstance(marker, Spam) for marker in markers)
    assert {(marker.event_origin.location, marker.event_origin.external_id) for marker in markers} == {
        (manual_origin.location, manual_origin.external_id),
        (auto_origin.location, auto_origin.external_id),
    }
    assert {marker.id for marker in markers} == {manual_record.id, auto_record.id}
