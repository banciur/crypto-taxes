# Lido Rewards Importer

`LidoImporter` translates the Lido rewards CSV export into single-leg `LedgerEvent`s. It reads `artifacts/lido.csv`, keeps only `type=reward` rows, converts `change_wei` with 18 decimals into `stETH` quantities, and emits Ethereum reward events on the configured wallet with ingestion source `lido_rewards_csv`.

Each emitted event uses `asset_id="stETH"` and `note="staking - Lido"`. The target wallet address is supplied by the caller; in the main pipeline it comes from `STAKING_REWARDS_WALLET_ADDRESS` in `data/.env`. Non-reward rows (`transfer`, `staking`) are ignored. Zero-quantity reward rows are skipped because ledger legs must be non-zero.
