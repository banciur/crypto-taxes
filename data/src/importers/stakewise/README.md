# Stakewise Rewards Importer

`StakewiseImporter` translates one or more Stakewise reward CSV exports into single-leg `LedgerEvent`s. Each CSV row becomes one reward event on a configured Ethereum wallet, with `location=ETHEREUM` and ingestion source `stakewise_rewards_csv`.

## Supported CSV shapes

- Stakewise v2 daily rewards: `Reward (rETH2)`, `Reward (USD)`, `Date (MM/DD/YYYY)`
- Stakewise v3 daily rewards: `Reward (ETH)`, `Reward (USD)`, `Date (YYYY-MM-DD)`

The importer ignores the USD column for now. It keeps reward quantities exactly as exported, including negative values and dust-sized amounts.

The target wallet address is supplied by the caller. In the main pipeline it comes from `STAKEWISE_WALLET_ADDRESS` in `data/.env`.

## Merge behavior

- The importer accepts multiple CSV paths.
- Rows are keyed by `reward date + asset`, so the v2/v3 boundary can keep both `rETH2` and `ETH` events on the same calendar day when needed.
- When the same `date + asset` appears in more than one file, the importer prefers the broader export (larger covered date span, then more rows).
- Zero-quantity rows still participate in conflict resolution, but they do not emit `LedgerEvent`s because ledger legs must be non-zero.
