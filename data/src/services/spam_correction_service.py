from __future__ import annotations

from db.corrections_store import SpamCorrectionRepository
from domain.correction import Spam, SpamCorrectionSource
from domain.ledger import EventOrigin


class SpamCorrectionService:
    def __init__(self, repo: SpamCorrectionRepository) -> None:
        self._repo = repo

    def list_active_manual(self) -> list[Spam]:
        return [record for record in self._repo.list_active() if record.source == SpamCorrectionSource.MANUAL]

    def create_manual(self, event_origin: EventOrigin) -> Spam:
        return self._repo.upsert_active(event_origin, SpamCorrectionSource.MANUAL)

    def delete_manual(self, event_origin: EventOrigin) -> None:
        self._repo.soft_delete(event_origin, SpamCorrectionSource.MANUAL)

    def list_active_markers(self) -> list[Spam]:
        return self._repo.list_active()
