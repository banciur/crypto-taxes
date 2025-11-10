# Kraken Ledger Importer

We are rebuilding the Kraken ledger ingestion from scratch. The goal is to take the raw CSV export from Kraken’s “Ledger” report, group rows by `refid`, and translate each group into a domain `LedgerEvent`. Nothing from the previous implementation is assumed correct—we will reintroduce event handling case by case with tests and documentation.

## Starting point

1. **CSV parsing:** `KrakenLedgerEntry` (Pydantic model) already normalizes timestamps to UTC and keeps numeric values in `Decimal`.
2. **Grouping:** `KrakenImporter._group_by_refid` bundles rows that share a `refid`. Each group represents one logical Kraken action (trade, transfer, earn reward, etc.). This grouping step is stable and will be reused throughout the rebuild.
3. **Event builder:** We are reintroducing logic incrementally inside `_build_event`, one refid pattern at a time, backed by tests and documentation.
4. **Exploration tooling:** `scripts/kraken_event_probe.py` runs the *real* importer against a CSV and reports which refids are unresolved, printing the first 15 groups (with row details). We’ll use that tool after each incremental change to verify coverage.
5. **Asset aliases:** Kraken sometimes reports suffixed tickers (e.g., `DOT28.S`, `USDC.M`). The importer normalizes a small allowlist of aliases up-front so that downstream logic sees canonical symbols (`DOT`, `USDC`, etc.).

As we implement each event type, this document will be expanded with the concrete rules, examples, and invariants for that scenario. For now, treat it as the canonical place to record decisions about new handlers.

## Implemented scenarios

### 1. Single-row `deposit`

- Applies when the refid group has a single ledger row of type `deposit` with a positive `amount`.
- If the `asset` is a fiat ticker (`EUR` or `USD`), the event is emitted as `EventType.DEPOSIT`.
- All other assets are treated as crypto deposits, which we model as `EventType.TRANSFER` (asset moving from an external wallet into Kraken without tax impact).
- A single positive leg is created for the deposited asset, and any reported fee on the same row is attached as a fee leg (negative quantity).

### 2. Single-row `withdrawal`

- Applies when the refid group has a single ledger row of type `withdrawal` with a negative `amount`.
- Fiat withdrawals (`EUR`, `USD`) emit `EventType.WITHDRAWAL`.
- Crypto withdrawals are modeled as `EventType.TRANSFER` (asset leaving Kraken to an external wallet).
- The main leg carries the reported amount (negative quantity). Fee rows on the same entry are emitted as fee legs (negative quantities) in the same asset.

### 3. Two-row `trade`

- Applies when a refid group contains exactly two `type="trade"` rows.
- The row with a negative `amount` becomes the sell leg; the positive `amount` row becomes the buy leg. Both legs are captured in `EventType.TRADE`.
- Fee values reported on either row become separate fee legs in the same wallet/asset (negative quantities).
- Timestamp for the event is the earliest timestamp across the two rows (Kraken typically uses the same instant for both).

### 4. Single-row `staking`

- Applies when a refid group has one `type="staking"` row with a positive `amount`.
- The event emits as `EventType.REWARD` with a positive leg for the staking asset (after alias normalization, if applicable).
- Any reported fee is emitted as a negative fee leg in the same asset/wallet.
- Historical anomalies: refids `STHFSYV-COKEV-2N3FK7` and `STFTGR6-35YZ3-ZWJDFO` contain negative staking amounts (Kraken logged the exit as `type="staking"` instead of `transfer`). These two refids are explicitly whitelisted so we still emit them as rewards despite the negative quantity.
