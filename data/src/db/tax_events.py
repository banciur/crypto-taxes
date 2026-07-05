from decimal import Decimal
from uuid import UUID

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, Session, mapped_column

from db.base import Base, DecimalAsString
from domain.ledger import DisposalId, LotId
from domain.tax_event import TaxEvent, TaxEventKind


class TaxEventOrm(Base):
    __tablename__ = "tax_events"

    source_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    taxable_gain: Mapped[Decimal] = mapped_column(DecimalAsString, nullable=False)


class TaxEventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_many(self, tax_events: list[TaxEvent]) -> list[TaxEvent]:
        orm_events = [
            TaxEventOrm(
                source_id=tax_event.source_id,
                kind=tax_event.kind.value,
                taxable_gain=tax_event.taxable_gain,
            )
            for tax_event in tax_events
        ]
        self._session.add_all(orm_events)
        self._session.commit()
        return tax_events

    def list(self) -> list[TaxEvent]:
        orm_events = self._session.query(TaxEventOrm).all()
        persisted: list[TaxEvent] = []
        for tax_event in orm_events:
            kind = TaxEventKind(tax_event.kind)
            source_id: DisposalId | LotId
            if kind == TaxEventKind.DISPOSAL:
                source_id = DisposalId(tax_event.source_id)
            else:
                source_id = LotId(tax_event.source_id)

            persisted.append(TaxEvent(source_id=source_id, kind=kind, taxable_gain=tax_event.taxable_gain))
        return persisted
