# API Layer Guidelines

## Purpose

- `src/api/` owns the FastAPI contract consumed by the UI.
- Keep route handlers thin: parse HTTP inputs, translate request/response shapes at the boundary, and delegate behavior to domain/services/repositories.
- Preserve the API contract when changing handlers; if the contract changes, update the relevant UI code and docs in the same change.

## Current Surface

- Event endpoints expose raw and corrected ledger data for the timeline UI.
- Correction endpoints expose one unified `LedgerCorrection` resource for discard, replacement, and opening-balance corrections.
- Accounts endpoints expose the merged account catalog used by the UI.

## Contract Notes

- `EventOrigin` (`location` + `external_id`) is the stable raw-event identity across API and UI.
- Corrections are deleted by `correction_id`; raw-event identity stays in the correction payload `sources`.
- `GET /accounts` returns the merged wallet + system exchange catalog. Records expose `account_chain_id`, `display_name`, and `skip_sync`.
- Multi-location configured wallets are expanded into one record per location, with `display_name` suffixed as `<configured name>:<first 3 lowercase letters of location>` (for example `Farming:eth`).
- Keep snake_case at the Python boundary; the UI API modules handle camelCase translation on the TypeScript side.
