from decimal import Decimal

from errors import CryptoTaxesError

from ..ledger import AssetId, LedgerEvent, LedgerLeg


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


class AcquisitionDisposalUnresolvedRatesError(AcquisitionDisposalValuationError):
    def __init__(self, message: str, *, asset_ids: frozenset[AssetId]) -> None:
        super().__init__(message)
        self.asset_ids = asset_ids


class AcquisitionDisposalLotMatchingError(AcquisitionDisposalProjectionError):
    pass
