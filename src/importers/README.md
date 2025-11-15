# Kraken Ledger Importer

`KrakenImporter` translates the raw CSV export from Kraken’s “Ledger” report into domain `LedgerEvent`s. The importer normalizes timestamps to UTC, converts numerics to `Decimal`, and collapses all Kraken sub-wallets into a single `wallet_id="kraken"` (spot, futures credit, staking, etc. are treated as one wallet in our tax model). Asset aliases such as `DOT28.S`, `USDC.M`, or `ETH2` are mapped to their canonical tickers up front so downstream systems see consistent asset IDs. While the importer will eventually sit alongside other data sources, you can already exercise it via `scripts/run_kraken_inventory.py` (`uv run scripts/run_kraken_inventory.py --csv path/to/ledger.csv`).

We expect most refids to be handled by the cases below; unknown patterns still raise so we can add explicit handling later.

## Ledger CSV essentials

The input CSV comes from Kraken’s web UI (“Ledger” report export). Each row contains the fields we rely on:

- `refid`: Kraken’s identifier for a logical action. Rows sharing a `refid` belong to the same scenario.
- `txid`: unique row identifier (used during preprocessing to drop internal transfers without disturbing other rows).
- `time`: naive timestamp in Kraken’s export format (`YYYY-MM-DD HH:MM:SS`), converted to UTC when parsed.
- `type` / `subtype`: primary classification (e.g., `trade`, `deposit`, `transfer`) plus optional subtype such as `spotfromfutures` or `tradespot`.
- `asset`: reported asset ticker (aliases such as `DOT28.S`, `USDC.M`, `ETH2` are normalized to canonical codes).
- `amount`: positive quantities mean inflows; negative values mean outflows.
- `fee`: fee charged on the same row; we emit it as a separate negative leg when non-zero.
- `wallet`: Kraken’s wallet label. We keep the value for traceability but all legs are emitted with `wallet_id="kraken"` to represent a consolidated exchange wallet.

## Import pipeline

1. **CSV parsing:** `KrakenLedgerEntry` (Pydantic model) normalizes each row (timestamp→UTC, numerics→`Decimal`, empty strings→zero).
2. **Preprocessing:** a pass over the flat ledger detects spot↔staking transfer pairs that net to zero and drops both rows so only economically meaningful events reach the builder.
3. **Grouping:** `_group_by_refid` bundles rows that share a `refid`. Each group represents one Kraken action (trade, transfer, reward, etc.).
4. **Event builder:** `_build_event` matches a refid pattern and emits the corresponding `LedgerEvent`. Fee columns become separate legs with `is_fee=True`.

## Scenario catalog

### Preprocessed multi-ref patterns

#### Internal staking transfers → skip

- Kraken spot↔staking moves show up as two separate refids (e.g., `spottostaking`, `stakingfromspot`, `stakingtospot`, `spotfromstaking`).
- A preprocessing pass pairs rows by normalized asset/amount within a five-day window; matched pairs are dropped entirely so inventory sees a single consolidated Kraken wallet.
- Unmatched rows are logged so they can be inspected manually.

### Single-row groups

#### `deposit` → emit event

- Applies when the refid group has a single ledger row of type `deposit` with a positive `amount`.
- If the `asset` is a fiat ticker (`EUR` or `USD`), the event is emitted as `EventType.DEPOSIT`.
- All other assets are treated as crypto deposits, which we model as `EventType.TRANSFER` (asset moving from an external wallet into Kraken without tax impact).
- A single positive leg is created for the deposited asset, and any reported fee on the same row is attached as a fee leg (negative quantity).

#### `withdrawal` → emit event

- Applies when the refid group has a single ledger row of type `withdrawal` with a negative `amount`.
- Fiat withdrawals (`EUR`, `USD`) emit `EventType.WITHDRAWAL`.
- Crypto withdrawals are modeled as `EventType.TRANSFER` (asset leaving Kraken to an external wallet).
- The main leg carries the reported amount (negative quantity). Fee rows on the same entry are emitted as fee legs (negative quantities) in the same asset.

#### `staking` → emit event

- Applies when a refid group has one `type="staking"` row with a positive `amount`.
- The event emits as `EventType.REWARD` with a positive leg for the staking asset (after alias normalization, if applicable).
- Any reported fee is emitted as a negative fee leg in the same asset/wallet.
- Historical anomalies: refids `STHFSYV-COKEV-2N3FK7` and `STFTGR6-35YZ3-ZWJDFO` contain negative staking amounts (Kraken logged the exit as `type="staking"` instead of `transfer`). These two refids are explicitly whitelisted so we still emit them as rewards despite the negative quantity.

#### `earn` reward → emit event

- Applies when the lone row has `type="earn"` and `subtype="reward"` with a positive amount.
- Emitted as `EventType.REWARD` with the asset/fee handling matching staking rewards.

#### `transfer` (`spotfromfutures`) → emit event

- Applies when a refid contains a single `type="transfer"` row whose `subtype="spotfromfutures"` and amount is positive.
- Represents Kraken crediting spot balances after futures adjustments/forks; emitted as `EventType.DROP` with a single positive leg (plus any fee legs, though fees have not been observed).

### Two-row groups

#### `trade`/`spend-receive` → emit event

- Applies when a refid group contains exactly two `type="trade"` rows **or** a `spend`/`receive` pair (Kraken sometimes encodes dust-sweeps or special conversions this way).
- The row with a negative `amount` becomes the sell leg; the positive `amount` row becomes the buy leg. Both legs are captured in `EventType.TRADE`.
- Fee values reported on either row become separate fee legs in the same wallet/asset (negative quantities).
- Timestamp for the event is the earliest timestamp across the two rows (Kraken typically uses the same instant for both).

#### `earn` migration → skip

- Applies when a refid group has two `type="earn"` rows and both rows have `subtype="migration"`.
- When the amounts cancel to zero (asset re-labeling with no economic impact), the importer drops the refid and returns `None`.
- If the legs do not net to zero an exception is raised so we can design an explicit handler.

#### `earn` allocation/deallocation → skip

- Applies to refids with two `type="earn"` rows whose subtypes are limited to `allocation` and/or `deallocation`.
- The importer requires the normalized asset to match and the amounts to net to zero; when these conditions hold it logs the internal wallet move and returns `None`.
- Non-zero nets raise so we can add explicit support.

#### Explicit refid skip

- `ELFI6E5-PNXZG-NSGNER` (four earn allocation/deallocation legs over months) is ignored because it only shuffles balances between Kraken earn sub-wallets with no economic impact.

Other refid patterns will surface as exceptions during imports; keep those failures so we can document and extend the importer with targeted handlers.
