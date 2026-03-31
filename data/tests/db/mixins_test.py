import time

from sqlalchemy import Engine, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from db.mixins import TimestampAuditMixin


class AuditTestBase(DeclarativeBase):
    pass


class AuditRowOrm(TimestampAuditMixin, AuditTestBase):
    __tablename__ = "audit_row_test"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)


def test_timestamp_audit_mixin_sets_insert_and_update_timestamps(
    db_engine: Engine,
) -> None:
    AuditTestBase.metadata.create_all(db_engine)
    try:
        with Session(db_engine) as session:
            row = AuditRowOrm(name="before", **AuditRowOrm.new_timestamp_audit_values())
            session.add(row)
            session.commit()

            inserted_created_at = row.created_at
            inserted_updated_at = row.updated_at

            assert inserted_created_at == inserted_updated_at

            time.sleep(0.01)
            row.name = "after"
            session.commit()

            assert row.created_at == inserted_created_at
            assert row.updated_at > inserted_updated_at
    finally:
        AuditTestBase.metadata.drop_all(db_engine)
