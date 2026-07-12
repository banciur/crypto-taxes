from enum import IntEnum

from config import BASE_CURRENCY_ASSET_ID, FIAT_CURRENCY_CODES, STABLE_ASSETS_BY_PEG

from ..ledger import AssetId

_STABLE_ASSET_IDS = frozenset(stable for stables in STABLE_ASSETS_BY_PEG.values() for stable in stables)


class ValuationTier(IntEnum):
    """How far an asset's EUR rate can be trusted, strongest tier first.

    The base currency is exact by definition, fiat comes from an FX quote, a stable adds a peg assumption on
    top of that quote, and everything else is a market price. Within an event the weakest tier present absorbs
    the balancing discrepancy while every stronger tier anchors.
    """

    BASE_CURRENCY = 0
    FIAT = 1
    STABLE = 2
    MARKET = 3


def valuation_tier(asset_id: AssetId) -> ValuationTier:
    if asset_id == BASE_CURRENCY_ASSET_ID:
        return ValuationTier.BASE_CURRENCY
    if asset_id in FIAT_CURRENCY_CODES:
        return ValuationTier.FIAT
    if asset_id in _STABLE_ASSET_IDS:
        return ValuationTier.STABLE
    return ValuationTier.MARKET


def is_reference_priced(asset_id: AssetId) -> bool:
    """Fiat and stables take their EUR rate from FX/peg reference data rather than a market quote, so a
    missing rate means the price data is broken instead of the asset being genuinely unpriceable."""
    return valuation_tier(asset_id) is not ValuationTier.MARKET


def is_fifo_tracked_asset(asset_id: AssetId) -> bool:
    return asset_id not in FIAT_CURRENCY_CODES
