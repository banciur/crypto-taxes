from datetime import datetime

from sqlalchemy import DateTime, Integer, String, delete
from sqlalchemy.orm import Mapped, Session, mapped_column

from db.base import SINGLETON_ROW_ID, Base
from domain.system_state import (
    SystemState,
    SystemStateError,
    SystemStateStage,
    SystemStateStatus,
)
from utils.misc import ensure_utc_datetime


class SystemStateOrm(Base):
    __tablename__ = "system_state"

    singleton_id: Mapped[int] = mapped_column(Integer, primary_key=True, default=SINGLETON_ROW_ID)
    status: Mapped[str] = mapped_column(String, nullable=False)
    stage: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    exception_type: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    traceback: Mapped[str | None] = mapped_column(String, nullable=True, default=None)


class SystemStateRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self) -> SystemState:
        row = self._session.get(SystemStateOrm, SINGLETON_ROW_ID)
        if row is None:
            return SystemState.not_run()

        return SystemState(
            status=SystemStateStatus(row.status),
            stage=self._to_stage(row.stage),
            started_at=ensure_utc_datetime(row.started_at),
            finished_at=ensure_utc_datetime(row.finished_at),
            error=self._to_error(row),
        )

    def replace(self, state: SystemState) -> SystemState:
        exception_type: str | None = None
        error_message: str | None = None
        traceback: str | None = None

        if state.error is not None:
            exception_type = state.error.exception_type
            error_message = state.error.message
            traceback = state.error.traceback

        self._session.execute(delete(SystemStateOrm))
        self._session.flush()
        self._session.expunge_all()
        self._session.add(
            SystemStateOrm(
                singleton_id=SINGLETON_ROW_ID,
                status=state.status.value,
                stage=self._stage_value(state.stage),
                started_at=state.started_at,
                finished_at=state.finished_at,
                exception_type=exception_type,
                error_message=error_message,
                traceback=traceback,
            )
        )
        self._session.commit()
        return state

    @staticmethod
    def _stage_value(stage: SystemStateStage | None) -> str | None:
        if stage is None:
            return None
        return stage.value

    @staticmethod
    def _to_stage(value: str | None) -> SystemStateStage | None:
        if value is None:
            return None
        return SystemStateStage(value)

    @staticmethod
    def _to_error(row: SystemStateOrm) -> SystemStateError | None:
        if row.exception_type is None:
            return None
        if row.error_message is None:
            raise ValueError("Persisted system state error is missing a message")

        return SystemStateError(
            exception_type=row.exception_type,
            message=row.error_message,
            traceback=row.traceback,
        )
