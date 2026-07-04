from decimal import Decimal

from errors import CryptoTaxesError

from ..ledger import LedgerEvent, LedgerLeg
from ..pricing import RequiredPriceUnavailableError


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


class AcquisitionDisposalValuationError(AcquisitionDisposalProjectionError):
    pass


class RequiredValuationPriceUnavailableError(AcquisitionDisposalValuationError):
    def __init__(self, *, pricing_error: RequiredPriceUnavailableError) -> None:
        super().__init__(
            "Required direct valuation price is unavailable: "
            f"base={pricing_error.base_id} quote={pricing_error.quote_id} "
            f"timestamp={pricing_error.timestamp.isoformat()}. {pricing_error.reason}",
        )
        self.pricing_error = pricing_error


class AcquisitionDisposalLotMatchingError(AcquisitionDisposalProjectionError):
    pass
