from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column

from utils.misc import utc_now


class TimestampAuditMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    @staticmethod
    def new_timestamp_audit_values() -> dict[str, datetime]:
        now = utc_now()
        return {
            "created_at": now,
            "updated_at": now,
        }
