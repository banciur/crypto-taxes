# crypto-taxes
Yet another unfinished system for tracking crypto transactions and calculating taxes - but I need something tailored for a stable farmer in Germany.

Also, it's 100% vibed by Codex — you've been warned :)

## Docs
- Current domain model: `doc/CURRENT.md`
- Contributing and agent workflow: `AGENTS.md`

## Repository layout
- `data/`: Python project (domain + ingestion/transforms + tests).
- `ui/`: Next.js app (web UI).
- `artifacts/`: local artifacts and caches (CSV exports, `accounts.json`, `transactions_cache.db`, etc.).
- `doc/`: domain reference and notes.
