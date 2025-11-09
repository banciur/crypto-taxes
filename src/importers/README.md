# Kraken Ledger Importer

We are rebuilding the Kraken ledger ingestion from scratch. The goal is to take the raw CSV export from Kraken’s “Ledger” report, group rows by `refid`, and translate each group into a domain `LedgerEvent`. Nothing from the previous implementation is assumed correct—we will reintroduce event handling case by case with tests and documentation.

## Starting point

1. **CSV parsing:** `KrakenLedgerEntry` (Pydantic model) already normalizes timestamps to UTC and keeps numeric values in `Decimal`.
2. **Grouping:** `KrakenImporter._group_by_refid` bundles rows that share a `refid`. Each group represents one logical Kraken action (trade, transfer, earn reward, etc.). This grouping step is stable and will be reused throughout the rebuild.
3. **Event builder placeholder:** `_build_event` currently raises; every new behavior will be added here (with supporting helpers/tests) once we understand a refid pattern.
4. **Exploration tooling:** `scripts/kraken_event_probe.py` runs the *real* importer against a CSV and reports which refids are unresolved, printing the first 15 groups (with row details). We’ll use that tool after each incremental change to verify coverage.

As we implement each event type, this document will be expanded with the concrete rules, examples, and invariants for that scenario. For now, treat it as the canonical place to record decisions about new handlers.
