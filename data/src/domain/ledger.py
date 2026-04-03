from __future__ import annotations

from abc import ABC
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, NewType
from uuid import UUID, uuid4

from pydantic import Field, StringConstraints, field_validator

from errors import CryptoTaxesError
from pydantic_base import StrictBaseModel

AssetId = NewType("AssetId", str)
DisposalId = NewType("DisposalId", UUID)
LedgerEventId = NewType("LedgerEventId", UUID)
LegId = NewType("LegId", UUID)
LotId = NewType("LotId", UUID)
WalletAddress = NewType("WalletAddress", str)
AccountChainId = NewType("AccountChainId", str)


class EventLocation(StrEnum):
    ETHEREUM = "ETHEREUM"
    ARBITRUM = "ARBITRUM"
    BASE = "BASE"
    OPTIMISM = "OPTIMISM"
    KRAKEN = "KRAKEN"
    COINBASE = "COINBASE"
    BINANCE = "BINANCE"
    INTERNAL = "INTERNAL"


class EventOrigin(StrictBaseModel):
    location: EventLocation
    external_id: Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]


class LedgerLeg(StrictBaseModel):
    """A single leg within an event.

    Quantity sign convention:
    - Positive quantity indicates an asset/position increase.
    - Negative quantity indicates an asset/position decrease.
    """

    id: LegId = LegId(Field(default_factory=uuid4))
    asset_id: AssetId
    quantity: Decimal
    account_chain_id: AccountChainId
    is_fee: bool = False

    @field_validator("quantity")
    @classmethod
    def _validate_quantity(cls, value: Decimal) -> Decimal:
        if value == 0:
            raise ValueError("LedgerLeg.quantity must be non-zero")
        return value


LegIdentity = tuple[AccountChainId, AssetId, bool]


class DuplicateLegIdentityError(CryptoTaxesError, ValueError):
    def __init__(self, duplicates: tuple[LegIdentity, ...]) -> None:
        self.duplicates = duplicates
        duplicates_summary = ", ".join(
            f"account={account_chain_id} asset={asset_id} is_fee={is_fee}"
            for account_chain_id, asset_id, is_fee in duplicates
        )
        super().__init__(f"AbstractEvent.legs contains duplicate leg identities: {duplicates_summary}")


class AbstractEvent(StrictBaseModel, ABC):
    timestamp: datetime
    legs: list[LedgerLeg] = Field(min_length=1)

    @field_validator("legs")
    @classmethod
    def _validate_unique_leg_identity(cls, legs: list[LedgerLeg]) -> list[LedgerLeg]:
        seen_leg_keys: set[LegIdentity] = set()
        duplicate_leg_keys: set[LegIdentity] = set()

        for leg in legs:
            leg_key = (leg.account_chain_id, leg.asset_id, leg.is_fee)
            if leg_key in seen_leg_keys:
                duplicate_leg_keys.add(leg_key)
                continue
            seen_leg_keys.add(leg_key)

        if duplicate_leg_keys:
            raise DuplicateLegIdentityError(tuple(sorted(duplicate_leg_keys)))

        return legs


class LedgerEvent(AbstractEvent):
    id: LedgerEventId = LedgerEventId(Field(default_factory=uuid4))

    event_origin: EventOrigin
    ingestion: Annotated[str, Field(min_length=1)]
    note: Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)] | None = None
