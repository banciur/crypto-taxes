from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Integer, String, Uuid, delete, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from db.models import Base, DecimalAsString
from domain.ledger import AccountChainId, AssetId, EventLocation, EventOrigin
from domain.wallet_tracking import (
    WalletBalance,
    WalletTrackingIssue,
    WalletTrackingState,
    WalletTrackingStatus,
)

CURRENT_STATE_ID = 1


class WalletTrackingStateOrm(Base):
    __tablename__ = "wallet_tracking_state"

    singleton_id: Mapped[int] = mapped_column(Integer, primary_key=True, default=CURRENT_STATE_ID)
    status: Mapped[str] = mapped_column(String, nullable=False)
    failed_origin_location: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    failed_origin_external_id: Mapped[str | None] = mapped_column(String, nullable=True, default=None)


class WalletTrackingBalanceOrm(Base):
    __tablename__ = "wallet_tracking_balances"

    account_chain_id: Mapped[str] = mapped_column(String, primary_key=True)
    asset_id: Mapped[str] = mapped_column(String, primary_key=True)
    balance: Mapped[Decimal] = mapped_column(DecimalAsString, nullable=False)


class WalletTrackingIssueOrm(Base):
    __tablename__ = "wallet_tracking_issues"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    event_origin_location: Mapped[str] = mapped_column(String, nullable=False)
    event_origin_external_id: Mapped[str] = mapped_column(String, nullable=False)
    account_chain_id: Mapped[str] = mapped_column(String, nullable=False)
    asset_id: Mapped[str] = mapped_column(String, nullable=False)
    attempted_delta: Mapped[Decimal] = mapped_column(DecimalAsString, nullable=False)
    available_balance: Mapped[Decimal] = mapped_column(DecimalAsString, nullable=False)
    missing_balance: Mapped[Decimal] = mapped_column(DecimalAsString, nullable=False)


class WalletTrackingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self) -> WalletTrackingState | None:
        state_row = self._session.get(WalletTrackingStateOrm, CURRENT_STATE_ID)
        if state_row is None:
            return None

        balance_rows = self._session.execute(
            select(WalletTrackingBalanceOrm).order_by(
                WalletTrackingBalanceOrm.account_chain_id.asc(),
                WalletTrackingBalanceOrm.asset_id.asc(),
            )
        ).scalars()
        issue_rows = self._session.execute(select(WalletTrackingIssueOrm)).scalars()

        return WalletTrackingState(
            status=WalletTrackingStatus(state_row.status),
            failed_event=self._to_event_origin(
                location=state_row.failed_origin_location,
                external_id=state_row.failed_origin_external_id,
            ),
            issues=[
                WalletTrackingIssue(
                    event=EventOrigin(
                        location=EventLocation(row.event_origin_location),
                        external_id=row.event_origin_external_id,
                    ),
                    account_chain_id=AccountChainId(row.account_chain_id),
                    asset_id=AssetId(row.asset_id),
                    attempted_delta=row.attempted_delta,
                    available_balance=row.available_balance,
                    missing_balance=row.missing_balance,
                )
                for row in issue_rows
            ],
            balances=[
                WalletBalance(
                    account_chain_id=AccountChainId(row.account_chain_id),
                    asset_id=AssetId(row.asset_id),
                    balance=row.balance,
                )
                for row in balance_rows
            ],
        )

    def replace(self, state: WalletTrackingState) -> WalletTrackingState:
        failed_location, failed_external_id = self._event_origin_parts(state.failed_event)

        self._session.execute(delete(WalletTrackingIssueOrm))
        self._session.execute(delete(WalletTrackingBalanceOrm))
        self._session.execute(delete(WalletTrackingStateOrm))
        self._session.flush()
        self._session.expunge_all()
        self._session.add(
            WalletTrackingStateOrm(
                singleton_id=CURRENT_STATE_ID,
                status=state.status.value,
                failed_origin_location=failed_location,
                failed_origin_external_id=failed_external_id,
            )
        )
        self._session.add_all(
            [
                WalletTrackingBalanceOrm(
                    account_chain_id=balance.account_chain_id,
                    asset_id=balance.asset_id,
                    balance=balance.balance,
                )
                for balance in state.balances
            ]
        )
        self._session.add_all(
            [
                WalletTrackingIssueOrm(
                    event_origin_location=issue.event.location.value,
                    event_origin_external_id=issue.event.external_id,
                    account_chain_id=issue.account_chain_id,
                    asset_id=issue.asset_id,
                    attempted_delta=issue.attempted_delta,
                    available_balance=issue.available_balance,
                    missing_balance=issue.missing_balance,
                )
                for issue in state.issues
            ]
        )
        self._session.commit()
        return state

    @staticmethod
    def _event_origin_parts(origin: EventOrigin | None) -> tuple[str | None, str | None]:
        if origin is None:
            return None, None
        return origin.location.value, origin.external_id

    @staticmethod
    def _to_event_origin(*, location: str | None, external_id: str | None) -> EventOrigin | None:
        if location is None or external_id is None:
            return None
        return EventOrigin(location=EventLocation(location), external_id=external_id)
