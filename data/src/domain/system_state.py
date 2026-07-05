from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic_base import StrictBaseModel


class SystemStateStatus(StrEnum):
    NOT_RUN = "NOT_RUN"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class SystemStateStage(StrEnum):
    RAW_IMPORT = "RAW_IMPORT"
    CORRECTIONS = "CORRECTIONS"
    WALLET_PROJECTION = "WALLET_PROJECTION"
    ACQUISITION_DISPOSAL = "ACQUISITION_DISPOSAL"
    TAX_COMPUTATION = "TAX_COMPUTATION"


class SystemStateError(StrictBaseModel):
    exception_type: str
    message: str
    traceback: str | None = None


class SystemState(StrictBaseModel):
    status: SystemStateStatus
    stage: SystemStateStage | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: SystemStateError | None = None

    @classmethod
    def not_run(cls) -> Self:
        return cls(status=SystemStateStatus.NOT_RUN)
