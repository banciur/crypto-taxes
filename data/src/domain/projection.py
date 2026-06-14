from enum import StrEnum


class ProjectionStatus(StrEnum):
    NOT_RUN = "NOT_RUN"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


__all__ = ["ProjectionStatus"]
