from pydantic import ConfigDict

from domain.ledger import AccountChainId, EventLocation
from pydantic_base import StrictBaseModel


class SystemAccount(StrictBaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    account_chain_id: AccountChainId
    name: str
    location: EventLocation


COINBASE_ACCOUNT_ID = AccountChainId("coinbase")
KRAKEN_ACCOUNT_ID = AccountChainId("kraken")

DEFAULT_SYSTEM_ACCOUNTS: tuple[SystemAccount, ...] = (
    SystemAccount(
        account_chain_id=COINBASE_ACCOUNT_ID,
        name="Coinbase",
        location=EventLocation.COINBASE,
    ),
    SystemAccount(
        account_chain_id=KRAKEN_ACCOUNT_ID,
        name="Kraken",
        location=EventLocation.KRAKEN,
    ),
)


__all__ = [
    "COINBASE_ACCOUNT_ID",
    "DEFAULT_SYSTEM_ACCOUNTS",
    "KRAKEN_ACCOUNT_ID",
    "SystemAccount",
]
