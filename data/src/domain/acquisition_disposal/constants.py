from config import FIAT_CURRENCY_CODES, STABLE_ASSETS_BY_PEG

from ..ledger import AssetId

_STABLE_ASSET_IDS = frozenset(stable for stables in STABLE_ASSETS_BY_PEG.values() for stable in stables)
VALUATION_ANCHOR_ASSET_IDS = FIAT_CURRENCY_CODES | _STABLE_ASSET_IDS


def is_valuation_anchor(asset_id: AssetId) -> bool:
    return asset_id in VALUATION_ANCHOR_ASSET_IDS


def is_fifo_tracked_asset(asset_id: AssetId) -> bool:
    return asset_id not in FIAT_CURRENCY_CODES
