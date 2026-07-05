# Kraken Scripts

Purpose of scripts in this folder:

- `kraken_event_probe.py`: runs the real `KrakenImporter` grouping/build logic across the full ledger CSV and reports resolved, skipped, and unresolved refid groups.
- `kraken_row_range_import.py`: feeds a selected CSV row range into `KrakenImporter` and prints the resulting events for focused debugging.
