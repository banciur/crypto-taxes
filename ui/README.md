# UI Guidelines

## UI Overview

- The page is split into a left toolbar and a main event section.
- The left toolbar contains the column chooser and date chooser.
- The main event section shows the selected lanes of ledger data plus the action bar for lane-level actions and feedback.

### Lane behavior

- `Raw events` shows imported ledger events before corrections are applied.
- `Corrections` shows one unified feed of persisted discard, replacement, and opening-balance corrections.
- `Corrected events` shows the ledger after unified corrections are applied.
- `Acquisitions / Disposals` shows the read-only acquisition/disposal projection as two card types in one lane, discriminated by the API's `ACQUISITION`/`DISPOSAL` kind. Cards are not selectable. Disposal cards derive cost-per-unit (`cost_basis_total / quantity_used`) and gain/loss (`proceeds_total - cost_basis_total`) in the UI; opening-lot linkage fields are intentionally not displayed.

### Supported actions

- Selection is available only for raw-backed event cards; selected cards drive discard and replacement creation from the action bar.
- Opening-balance creation is action-bar driven and does not require any selected source events.
- Removing a correction is initiated from the corresponding card in the `Corrections` lane.
- Price overrides are authored per leg on `Corrected events` cards: a leg without an override offers `Set price`, and a leg with one shows its EUR-per-unit rate plus a remove control. An override prices one asset of one corrected event, so it is shown on every leg carrying that asset. The affordance is deliberately absent from the `Raw events` lane, because a passthrough event shares its origin across both lanes while an override only ever prices the corrected one.
- The price override form exposes a per-unit rate and a total EUR value; editing either recomputes the other from the absolute leg quantity. Only the rate is sent to the API, so the conversion is a convenience calculator. A zero-quantity leg disables the total-value field.
- Hovering a source-backed correction activates shared source-highlighting state that colors the listed correction sources and every matching raw/corrected event card.
- The date chooser updates the visible timeline day by scrolling the virtualized event list.
- The column chooser updates which lanes are loaded and rendered.
- Correction and price-override mutations refresh the server-rendered lane data immediately; corrected pipeline outputs still require a manual rerun outside the UI.

## UI Structure

- `src/app/page.tsx` loads the selected columns, the merged accounts catalog, the latest system state, and wallet balances from the backend, groups all loaded lane items by timestamp bucket, and wires the page-level providers.
- `src/components/SystemState/SystemStateSection.tsx` renders the latest main-flow status, stage, timestamps, known error details, and unexpected tracebacks.
- `src/components/Events/` owns event selection state, correction creation/removal actions, and the action bar shown above the timeline. The directory keeps the React component in `Events.tsx`, selection state in `useEventSelection.ts`, and pure event-derivation helpers in `selectableEvents.ts`.
- `src/components/Events/ReplacementEditorModal.tsx` owns the structured replacement-creation form, including UTC timestamp editing, leg authoring, and note capture.
- `src/components/Events/PriceOverrideEditorModal.tsx` owns the price-override creation form and the rate/total-value conversion.
- `src/components/Events/OpeningBalanceEditorModal.tsx` owns the source-less opening-balance creation form.
- `src/components/VirtualizedDateSections.tsx` virtualizes timeline rows for rendering performance; all selected column data is still loaded in memory up front.
- `src/components/TimestampBucketRow.tsx` renders one timestamp bucket across the currently selected columns and dispatches lane items to the appropriate card component.
- `src/components/LedgerEventCard.tsx` is the shared card UI for raw and corrected ledger events.
- `src/components/AcquisitionDisposalCard.tsx` renders both acquisition and disposal cards for the `Acquisitions / Disposals` lane, branching on the item `kind`.
- `src/components/LedgerLegList.tsx` is the shared ledger-leg renderer for event and correction cards; it keeps leg rows in `wallet -> token -> amount` order and centralizes fee/quantity presentation.
- `src/contexts/AccountNamesContext.tsx` exposes the merged account dataset plus account-label resolution helpers to client components.
- `src/contexts/PriceOverridesContext.tsx` indexes the stored price overrides by `(event origin, asset)` so event cards can look one up without prop drilling.
- `src/components/LedgerLegList.tsx` takes an optional `renderLegAccessory` render prop so a lane can attach per-leg affordances (price overrides) without the shared leg renderer knowing about them.

## Architecture and Integration

### Communication with the backend

- The UI talks to FastAPI through the same-origin `/api/crypto-taxes/*` rewrite in `next.config.ts`.
- Put reusable API transport in `src/api/core.ts` and keep backend communication split into focused resource files under `src/api/` (ex. `events.ts`, `accounts.ts` etc.). Both server and client code should consume those shared API modules.
- `src/api/core.ts` owns the request/response case translation at the API boundary. Endpoint modules should expose camelCase TypeScript shapes and avoid duplicating snake_case DTO mirror types.

### API contract

- Base URL comes from `CRYPTO_TAXES_API_URL` (defaults to `http://localhost:8000`).
- `GET /accounts` returns the merged wallet + system exchange catalog; records expose `account_chain_id`, `display_name`, and `skip_sync`.
- `GET /system-state` returns the latest main-flow run status with optional stage, first error details, and traceback.
- `GET /wallet-balances` returns the current corrected-ledger wallet balances.
- `GET /acquisition-disposal` returns the acquisition/disposal projection as a pre-sorted list of `ACQUISITION` and `DISPOSAL` items sharing common fields (`event_origin`, `account_chain_id`, `asset_id`, `is_fee`, `timestamp`) plus kind-specific decimal fields.
- Ledger leg quantities remain string-backed decimal values at the API boundary.
- `GET /corrections` returns feed for discard, replacement, and opening-balance items.
- Source-backed corrections may be saved without legs; they consume the selected raw sources without emitting a corrected synthetic event.
- Correction mutations refresh the server-rendered lane data after they are complete.
- `GET /price-overrides` returns a flat list of stored overrides (`event_origin`, `asset_id`, `rate_eur`, optional `note`). It does not report whether an override still matches a corrected event; a stale one fails the pipeline and surfaces through `GET /system-state`.
- `POST /price-overrides` answers `409` when the asset already has an override on that event.
- After manual correction changes, the ingestion pipeline still needs to be rerun manually for corrected pipeline outputs to reflect those changes end-to-end.

### Decimal handling

- Keep backend decimal values as strings in shared UI types and API modules. Do not convert them to native `Number` values at the boundary.
- When UI code needs to format, normalize, validate, or inspect the sign or zero state of decimal values, use shared helpers in `src/lib/decimalStrings.ts`.
- When rendering ledger leg quantities, use `src/lib/ledgerLegQuantity.ts` so quantity formatting and sign-based presentation stay consistent across components.

## Technical Workflow

### Tech stack

- Package manager is pnpm;
- Next.js 16 (React 19, TypeScript) app using the App Router; source code lives in `ui/src` with `@/*` aliasing to `src/*`.
- Runtime is a modern JS environment; feel free to use new ECMAScript features without downleveling or adding polyfills.
- Styling is Bootstrap 5, consumed through `react-bootstrap` (global import in `src/app/layout.tsx`); prefer `react-bootstrap` components and scoped styles (CSS modules or `globals.css`) for custom tweaks.
- Prettier 3 for formatting;
- ESLint is configured with Next core web vitals plus Prettier compatibility (`eslint.config.mjs`); keep new code aligned with those rules.

### Development commands

- Run UI commands from `ui/` (`cd ui`).
- `pnpm prettier` formats the UI codebase with Prettier.
- `pnpm lint` runs ESLint.
- `pnpm types` runs `tsc --noEmit`.

### Suggested workflow

- Start in `ui/`.
- **ALWAYS** Before finishing a change, run `pnpm prettier`, `pnpm lint`, and `pnpm types`.
