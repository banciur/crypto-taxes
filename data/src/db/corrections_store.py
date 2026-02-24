from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, String, UniqueConstraint, Uuid, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from config import CORRECTIONS_DB_FILE
from domain.correction import CorrectionId, Spam, SpamCorrectionSource
from domain.ledger import EventLocation, EventOrigin

CORRECTIONS_DB_PATH = CORRECTIONS_DB_FILE


class CorrectionsBase(DeclarativeBase):
    pass


class SpamCorrectionOrm(CorrectionsBase):
    __tablename__ = "spam_corrections"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    origin_location: Mapped[str] = mapped_column(String, nullable=False)
    origin_external_id: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("origin_location", "origin_external_id", "source", name="uq_spam_corrections_origin_source"),
        Index("ix_spam_corrections_origin", "origin_location", "origin_external_id"),
    )


class SpamCorrectionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_active(self) -> list[Spam]:
        stmt = (
            select(SpamCorrectionOrm)
            .where(SpamCorrectionOrm.deleted_at.is_(None))
            .order_by(
                SpamCorrectionOrm.origin_location.asc(),
                SpamCorrectionOrm.origin_external_id.asc(),
                SpamCorrectionOrm.source.asc(),
            )
        )
        rows = self._session.execute(stmt).scalars().all()
        return [self._to_domain(row) for row in rows]

    def get_by_origin_and_source(
        self,
        event_origin: EventOrigin,
        source: SpamCorrectionSource,
    ) -> Spam | None:
        stmt = (
            select(SpamCorrectionOrm)
            .where(
                SpamCorrectionOrm.origin_location == event_origin.location.value,
                SpamCorrectionOrm.origin_external_id == event_origin.external_id,
                SpamCorrectionOrm.source == source.value,
            )
            .limit(1)
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        if row is None:
            return None
        return self._to_domain(row)

    def upsert_active(self, event_origin: EventOrigin, source: SpamCorrectionSource) -> Spam:
        stmt = (
            select(SpamCorrectionOrm)
            .where(
                SpamCorrectionOrm.origin_location == event_origin.location.value,
                SpamCorrectionOrm.origin_external_id == event_origin.external_id,
                SpamCorrectionOrm.source == source.value,
            )
            .limit(1)
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        if row is None:
            row = SpamCorrectionOrm(
                origin_location=event_origin.location.value,
                origin_external_id=event_origin.external_id,
                source=source.value,
                deleted_at=None,
            )
            self._session.add(row)
        elif row.deleted_at is not None:
            row.deleted_at = None

        self._session.commit()
        self._session.refresh(row)
        return self._to_domain(row)

    def soft_delete(self, event_origin: EventOrigin, source: SpamCorrectionSource) -> bool:
        stmt = (
            select(SpamCorrectionOrm)
            .where(
                SpamCorrectionOrm.origin_location == event_origin.location.value,
                SpamCorrectionOrm.origin_external_id == event_origin.external_id,
                SpamCorrectionOrm.source == source.value,
            )
            .limit(1)
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        if row is None or row.deleted_at is not None:
            return False

        row.deleted_at = datetime.now(timezone.utc)
        self._session.commit()
        return True

    @staticmethod
    def _to_domain(row: SpamCorrectionOrm) -> Spam:
        deleted_at = row.deleted_at
        if deleted_at is not None and deleted_at.tzinfo is None:
            deleted_at = deleted_at.replace(tzinfo=timezone.utc)
        return Spam(
            id=CorrectionId(row.id),
            event_origin=EventOrigin(
                location=EventLocation(row.origin_location),
                external_id=row.origin_external_id,
            ),
            source=SpamCorrectionSource(row.source),
            deleted_at=deleted_at,
        )


def init_corrections_db(
    echo: bool = False, *, db_file: str | Path = CORRECTIONS_DB_PATH, reset: bool = False
) -> Session:
    path = Path(db_file)
    if reset and path.exists():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(f"sqlite:///{path}", echo=echo)
    CorrectionsBase.metadata.create_all(engine)
    return sessionmaker(engine)()
