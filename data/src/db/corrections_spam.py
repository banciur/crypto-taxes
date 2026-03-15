from __future__ import annotations

from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Index, String, UniqueConstraint, Uuid, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from db.corrections_common import CorrectionsBase
from domain.correction import CorrectionId, Spam
from domain.ledger import EventLocation, EventOrigin


class SpamCorrectionSource(StrEnum):
    MANUAL = "MANUAL"
    AUTO_MORALIS = "AUTO_MORALIS"


class SpamCorrectionOrm(CorrectionsBase):
    __tablename__ = "spam_corrections"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    origin_location: Mapped[str] = mapped_column(String, nullable=False)
    origin_external_id: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("origin_location", "origin_external_id", name="uq_spam_corrections_origin"),
        Index("ix_spam_corrections_origin", "origin_location", "origin_external_id"),
    )


class SpamCorrectionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self) -> list[Spam]:
        stmt = (
            select(SpamCorrectionOrm)
            .where(SpamCorrectionOrm.is_deleted.is_(False))
            .order_by(
                SpamCorrectionOrm.origin_location.asc(),
                SpamCorrectionOrm.origin_external_id.asc(),
            )
        )
        rows = self._session.execute(stmt).scalars().all()
        return [self._to_domain(row) for row in rows]

    def mark_as_spam(
        self,
        event_origin: EventOrigin,
        source: SpamCorrectionSource = SpamCorrectionSource.MANUAL,
        *,
        skip_if_exists: bool = False,
    ) -> None:
        stmt = select(SpamCorrectionOrm).where(
            SpamCorrectionOrm.origin_location == event_origin.location.value,
            SpamCorrectionOrm.origin_external_id == event_origin.external_id,
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        if row is None:
            row = SpamCorrectionOrm(
                origin_location=event_origin.location.value,
                origin_external_id=event_origin.external_id,
                source=source.value,
                is_deleted=False,
            )
            self._session.add(row)
            self._session.commit()
            return

        if skip_if_exists:
            return

        row.source = source.value
        row.is_deleted = False
        self._session.commit()

    def remove_spam_mark(self, event_origin: EventOrigin) -> None:
        stmt = select(SpamCorrectionOrm).where(
            SpamCorrectionOrm.origin_location == event_origin.location.value,
            SpamCorrectionOrm.origin_external_id == event_origin.external_id,
            SpamCorrectionOrm.is_deleted.is_(False),
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        if row is not None:
            row.is_deleted = True
            self._session.commit()

    @staticmethod
    def _to_domain(row: SpamCorrectionOrm) -> Spam:
        return Spam(
            id=CorrectionId(row.id),
            event_origin=EventOrigin(
                location=EventLocation(row.origin_location),
                external_id=row.origin_external_id,
            ),
        )
