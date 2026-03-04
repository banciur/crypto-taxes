from __future__ import annotations

from functools import cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
ACCOUNTS_PATH = ARTIFACTS_DIR / "accounts.json"
TRANSACTIONS_CACHE_DB_PATH = ARTIFACTS_DIR / "transactions_cache.db"
DB_PATH = ARTIFACTS_DIR / "crypto_taxes.db"
CORRECTIONS_DB_PATH = ARTIFACTS_DIR / "corrections.db"


class AppSettings(BaseSettings):
    coindesk_api_key: str
    open_exchange_rates_app_id: str
    moralis_api_key: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@cache
def config() -> AppSettings:
    return AppSettings()  # type: ignore[call-arg]
