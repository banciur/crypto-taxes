from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Index, String, UniqueConstraint, Uuid, create_engine, select
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
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("origin_location", "origin_external_id", "source", name="uq_spam_corrections_origin_source"),
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
                SpamCorrectionOrm.source.asc(),
            )
        )
        rows = self._session.execute(stmt).scalars().all()
        return [self._to_domain(row) for row in rows]

    def mark_as_spam(self, event_origin: EventOrigin, source: SpamCorrectionSource) -> Spam:
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
                is_deleted=False,
            )
            self._session.add(row)
        elif row.is_deleted:
            row.is_deleted = False

        self._session.commit()
        self._session.refresh(row)
        return self._to_domain(row)

    def remove_spam_mark(self, event_origin: EventOrigin) -> None:
        stmt = select(SpamCorrectionOrm).where(
            SpamCorrectionOrm.origin_location == event_origin.location.value,
            SpamCorrectionOrm.origin_external_id == event_origin.external_id,
            SpamCorrectionOrm.is_deleted.is_(False),
        )
        rows = self._session.execute(stmt).scalars().all()
        for row in rows:
            row.is_deleted = True
        if rows:
            self._session.commit()

    @staticmethod
    def _to_domain(row: SpamCorrectionOrm) -> Spam:
        return Spam(
            id=CorrectionId(row.id),
            event_origin=EventOrigin(
                location=EventLocation(row.origin_location),
                external_id=row.origin_external_id,
            ),
            source=SpamCorrectionSource(row.source),
            is_deleted=row.is_deleted,
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
