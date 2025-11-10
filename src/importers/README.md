# Kraken Ledger Importer

We are rebuilding the Kraken ledger ingestion from scratch. The goal is to take the raw CSV export from Kraken’s “Ledger” report, group rows by `refid`, and translate each group into a domain `LedgerEvent`. Nothing from the previous implementation is assumed correct—we will reintroduce event handling case by case with tests and documentation.

## Starting point

1. **CSV parsing:** `KrakenLedgerEntry` (Pydantic model) already normalizes timestamps to UTC and keeps numeric values in `Decimal`.
2. **Grouping:** `KrakenImporter._group_by_refid` bundles rows that share a `refid`. Each group represents one logical Kraken action (trade, transfer, earn reward, etc.). This grouping step is stable and will be reused throughout the rebuild.
3. **Event builder:** We are reintroducing logic incrementally inside `_build_event`, one refid pattern at a time, backed by tests and documentation.
4. **Exploration tooling:** `scripts/kraken_event_probe.py` runs the *real* importer against a CSV and reports which refids are unresolved, printing the first 15 groups (with row details). We’ll use that tool after each incremental change to verify coverage.

As we implement each event type, this document will be expanded with the concrete rules, examples, and invariants for that scenario. For now, treat it as the canonical place to record decisions about new handlers.

## Implemented scenarios

### 1. Single-row `deposit`

- Applies when the refid group has a single ledger row of type `deposit` with a positive `amount`.
- If the `asset` is a fiat ticker (`EUR` or `USD`), the event is emitted as `EventType.DEPOSIT`.
- All other assets are treated as crypto deposits, which we model as `EventType.TRANSFER` (asset moving from an external wallet into Kraken without tax impact).
- A single positive leg is created for the deposited asset, and any reported fee on the same row is attached as a fee leg (negative quantity).
