from decimal import Decimal

from sqlalchemy import String, delete, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from db.base import Base, DecimalAsString
from domain.ledger import AccountChainId, AssetId
from domain.wallet_projection import WalletBalance


class WalletBalanceOrm(Base):
    __tablename__ = "wallet_balances"

    account_chain_id: Mapped[str] = mapped_column(String, primary_key=True)
    asset_id: Mapped[str] = mapped_column(String, primary_key=True)
    balance: Mapped[Decimal] = mapped_column(DecimalAsString, nullable=False)


class WalletBalanceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self) -> list[WalletBalance]:
        rows = self._session.execute(
            select(WalletBalanceOrm).order_by(
                WalletBalanceOrm.account_chain_id.asc(),
                WalletBalanceOrm.asset_id.asc(),
            )
        ).scalars()
        return [
            WalletBalance(
                account_chain_id=AccountChainId(row.account_chain_id),
                asset_id=AssetId(row.asset_id),
                balance=row.balance,
            )
            for row in rows
        ]

    def replace(self, balances: list[WalletBalance]) -> list[WalletBalance]:
        self._session.execute(delete(WalletBalanceOrm))
        self._session.flush()
        self._session.expunge_all()
        self._session.add_all(
            [
                WalletBalanceOrm(
                    account_chain_id=balance.account_chain_id,
                    asset_id=balance.asset_id,
                    balance=balance.balance,
                )
                for balance in balances
            ]
        )
        self._session.commit()
        return balances
