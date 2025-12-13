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
- `fee`: fee charged on the same row. Depending on the scenario, it is netted into the credited/debited leg or rebalanced between the `outside` and `kraken` wallets.
- `wallet`: Kraken’s wallet label. We keep the value for traceability but all legs are emitted with `wallet_id="kraken"` to represent a consolidated exchange wallet.

## Import pipeline

1. **CSV parsing:** `KrakenLedgerEntry` (Pydantic model) normalizes each row (timestamp→UTC, numerics→`Decimal`, empty strings→zero).
2. **Preprocessing:** a pass over the flat ledger detects spot↔staking transfer pairs that net to zero and drops both rows so only economically meaningful events reach the builder.
3. **Grouping:** `_group_by_refid` bundles rows that share a `refid`. Each group represents one Kraken action (trade, transfer, reward, etc.).
4. **Event builder:** `_build_event` matches a refid pattern and emits the corresponding `LedgerEvent`. Fees are netted or applied via the `outside`/`kraken` legs per the scenarios below.

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
- Two legs are emitted: `wallet_id="outside"` spends the reported `amount` (negative leg) and `wallet_id="kraken"` receives the net (`amount - fee`). Fees do not emit standalone legs; they are already accounted for in the net transfer into Kraken.

#### `withdrawal` → emit event

- Applies when the refid group has a single ledger row of type `withdrawal` with a negative `amount`.
- Fiat withdrawals (`EUR`, `USD`) emit `EventType.WITHDRAWAL`.
- Crypto withdrawals are modeled as `EventType.TRANSFER` (asset leaving Kraken to an external wallet).
- Two legs are emitted: `wallet_id="kraken"` spends the `amount` plus any fee (`amount - fee`, still negative) and `wallet_id="outside"` receives `abs(amount)`. The recipient leg therefore matches what arrives externally while Kraken records the extra outflow that covered fees.

#### `staking` → emit event

- Applies when a refid group has one `type="staking"` row with a positive `amount`.
- The event emits as `EventType.REWARD` with a positive leg for the staking asset (after alias normalization, if applicable).
- Any reported fee is netted into the reward quantity (the credited amount is `amount - fee`).
- Historical anomalies: refids `STHFSYV-COKEV-2N3FK7` and `STFTGR6-35YZ3-ZWJDFO` contain negative staking amounts (Kraken logged the exit as `type="staking"` instead of `transfer`). These two refids are explicitly whitelisted so we still emit them as rewards despite the negative quantity.

#### `earn` reward → emit event

- Applies when the lone row has `type="earn"` and `subtype="reward"` with a positive amount.
- Emitted as `EventType.REWARD`; any fee is netted into the credited quantity just like staking rewards.

#### `transfer` (`spotfromfutures`) → emit event

- Applies when a refid contains a single `type="transfer"` row whose `subtype="spotfromfutures"` and amount is positive.
- Represents Kraken crediting spot after drops/forks; emitted as `EventType.REWARD` with a single positive leg.

### Two-row groups

#### `trade`/`spend-receive` → emit event

- Applies when a refid group contains exactly two `type="trade"` rows **or** a `spend`/`receive` pair (Kraken sometimes encodes dust-sweeps or special conversions this way).
- The row with a negative `amount` becomes the sell leg; the positive `amount` row becomes the buy leg. Both legs are captured in `EventType.TRADE`.
- Fee values reported on either row are netted into that leg’s quantity (e.g., a buy row with `fee` reduces the acquired quantity).
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
