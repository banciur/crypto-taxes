from ..ledger import AssetId

BASE_CURRENCY_ASSET_ID = AssetId("EUR")
VALUATION_FIAT_ANCHOR_ASSET_IDS = frozenset(
    {
        BASE_CURRENCY_ASSET_ID,
        AssetId("USD"),
    }
)
VALUATION_STABLE_ANCHOR_ASSET_IDS = frozenset(
    {
        AssetId("USDC"),
        AssetId("USDT"),
        AssetId("GHO"),
    }
)
VALUATION_ANCHOR_ASSET_IDS = VALUATION_FIAT_ANCHOR_ASSET_IDS | VALUATION_STABLE_ANCHOR_ASSET_IDS


def is_valuation_anchor(asset_id: AssetId) -> bool:
    return asset_id in VALUATION_ANCHOR_ASSET_IDS


def is_fifo_tracked_asset(asset_id: AssetId) -> bool:
    return asset_id not in VALUATION_FIAT_ANCHOR_ASSET_IDS
