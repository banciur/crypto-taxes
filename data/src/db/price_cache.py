from datetime import datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from db.base import DecimalAsString
from db.session import init_db_session
from domain.ledger import AssetId
from domain.pricing import PriceRecord
from utils.misc import ensure_utc_datetime


class PriceCacheBase(DeclarativeBase):
    pass


class PriceEdgeOrm(PriceCacheBase):
    __tablename__ = "price_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    base_id: Mapped[str] = mapped_column(String, nullable=False)
    quote_id: Mapped[str] = mapped_column(String, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rate: Mapped[Decimal | None] = mapped_column(DecimalAsString, nullable=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("base_id", "quote_id", "valid_from", name="uq_price_edges_base_quote_valid_from"),
        Index("ix_price_edges_fetched_at", "fetched_at"),
    )


def init_price_cache_db(*, db_path: Path, echo: bool = False, reset: bool = False) -> Session:
    return init_db_session(
        db_path=db_path,
        metadata=PriceCacheBase.metadata,
        echo=echo,
        reset=reset,
    )


class PriceCacheRepository:
    def __init__(self, session: Session):
        self.session = session

    def read(self, base_id: AssetId, quote_id: AssetId, timestamp: datetime) -> PriceRecord | None:
        target_timestamp = ensure_utc_datetime(timestamp)
        stmt = (
            select(PriceEdgeOrm)
            .where(
                PriceEdgeOrm.base_id == base_id,
                PriceEdgeOrm.quote_id == quote_id,
                PriceEdgeOrm.valid_from <= target_timestamp,
                PriceEdgeOrm.valid_to > target_timestamp,
            )
            .order_by(PriceEdgeOrm.fetched_at.desc(), PriceEdgeOrm.id.desc())
            .limit(1)
        )
        row = self.session.execute(stmt).scalar_one_or_none()
        if row is None:
            return None

        return PriceRecord(
            base_id=AssetId(row.base_id),
            quote_id=AssetId(row.quote_id),
            rate=row.rate,
            source=row.source,
            valid_from=ensure_utc_datetime(row.valid_from),
            valid_to=ensure_utc_datetime(row.valid_to),
            fetched_at=ensure_utc_datetime(row.fetched_at),
        )

    def write(
        self,
        record: PriceRecord,
    ) -> None:
        row = {
            "base_id": record.base_id,
            "quote_id": record.quote_id,
            "valid_from": ensure_utc_datetime(record.valid_from),
            "valid_to": ensure_utc_datetime(record.valid_to),
            "rate": record.rate,
            "source": record.source,
            "fetched_at": ensure_utc_datetime(record.fetched_at),
        }
        stmt = insert(PriceEdgeOrm).values(row)
        stmt = stmt.on_conflict_do_update(
            index_elements=["base_id", "quote_id", "valid_from"],
            set_={
                "valid_to": stmt.excluded.valid_to,
                "rate": stmt.excluded.rate,
                "source": stmt.excluded.source,
                "fetched_at": stmt.excluded.fetched_at,
            },
        )
        self.session.execute(stmt)
        self.session.commit()
