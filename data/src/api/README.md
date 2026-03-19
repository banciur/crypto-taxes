# API Layer Guidelines

## Purpose

- `src/api/` owns the FastAPI contract consumed by the UI.
- Keep route handlers thin: parse HTTP inputs, translate request/response shapes at the boundary, and delegate behavior to domain/services/repositories.
- Preserve the API contract when changing handlers; if the contract changes, update the relevant UI code and docs in the same change.

## Current Surface

- Event endpoints expose raw, seed, and corrected ledger data for the timeline UI.
- Spam correction endpoints create and remove raw-event spam markers keyed by `EventOrigin`.
- Replacement correction endpoints list, create, and delete persisted replacement corrections.
- Accounts endpoints expose the merged account catalog used by the UI.

## Contract Notes

- `EventOrigin` (`location` + `external_id`) is the stable raw-event identity across API and UI.
- Path-based delete routes that address raw events should be keyed by `EventOrigin`.
- `GET /accounts` returns the merged wallet + system exchange catalog. Records expose `account_chain_id`, `name`, and `skip_sync`.
- Keep snake_case at the Python boundary; the UI API modules handle camelCase translation on the TypeScript side.
