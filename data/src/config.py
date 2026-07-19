from functools import cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from domain.ledger import AssetId

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
ACCOUNTS_PATH = ARTIFACTS_DIR / "accounts.json"
TRANSACTIONS_CACHE_DB_PATH = ARTIFACTS_DIR / "transactions_cache.db"
PRICE_CACHE_DB_PATH = ARTIFACTS_DIR / "price_cache.db"
PRICE_OVERRIDES_DB_PATH = ARTIFACTS_DIR / "price_overrides.db"
CMC_CONFIG_PATH = ARTIFACTS_DIR / "cmc_config.json"
DB_PATH = ARTIFACTS_DIR / "crypto_taxes.db"
CORRECTIONS_DB_PATH = ARTIFACTS_DIR / "corrections.db"

# Pricing model configuration.
BASE_CURRENCY_ASSET_ID = AssetId("EUR")
NUMERAIRE_ASSET_ID = AssetId("USD")
FIAT_CURRENCY_CODES = frozenset({AssetId("EUR"), AssetId("USD")})

STABLE_ASSETS_BY_PEG: dict[AssetId, frozenset[AssetId]] = {
    AssetId("USD"): frozenset({AssetId("USDC"), AssetId("USDT"), AssetId("DAI"), AssetId("GHO")}),
    AssetId("EUR"): frozenset({AssetId("EURC"), AssetId("EUR-T")}),
}

# Assets that take another asset's market price 1:1, keyed by the asset supplying that price.
ASSETS_PRICED_AS: dict[AssetId, frozenset[AssetId]] = {
    AssetId("ETH"): frozenset({AssetId("RETH2")}),
    AssetId("USDC"): frozenset({AssetId("AARBUSDCN")}),
}

# Debt/liability tokens that take another asset's market price with the sign flipped, keyed by the
# asset supplying that price. Holding a borrowed-asset debt token is owing the underlying, so its EUR
# value is the negative of the underlying's. Keys are uppercase to match the price service's
# normalized lookup.
ASSETS_PRICED_AS_NEGATED: dict[AssetId, frozenset[AssetId]] = {
    AssetId("WSTETH"): frozenset({AssetId("VARIABLEDEBTARBWSTETH")}),
    AssetId("WETH"): frozenset({AssetId("VARIABLEDEBTARBWETH"), AssetId("VARIABLEDEBTBASWETH")}),
    AssetId("GHO"): frozenset({AssetId("VARIABLEDEBTETHGHO")}),
    AssetId("USDC"): frozenset({AssetId("EVARIABLEDEBTBASEUSDC")}),
}


class AppSettings(BaseSettings):
    coinmarketcap_api_key: str
    coinmarketcap_high_resolution_days: int = 30
    open_exchange_rates_app_id: str
    moralis_api_key: str
    coinbase_key_name: str
    coinbase_key_prv: str
    staking_rewards_wallet_address: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@cache
def config() -> AppSettings:
    return AppSettings()  # type: ignore[call-arg]
