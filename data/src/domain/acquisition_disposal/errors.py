from __future__ import annotations

from decimal import Decimal

from errors import CryptoTaxesError

from ..ledger import LedgerEvent, LedgerLeg


class AcquisitionDisposalProjectionError(CryptoTaxesError):
    def __init__(
        self,
        message: str,
        *,
        leg: LedgerLeg | None = None,
        event: LedgerEvent | None = None,
        quantity_needed: Decimal | None = None,
    ) -> None:
        super().__init__(message)
        self.leg = leg
        self.event = event
        self.quantity_needed = quantity_needed
