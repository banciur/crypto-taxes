# UI Guidelines

## UI Overview

- The page is split into a left toolbar and a main event section.
- The left toolbar contains the column chooser and date chooser.
- The main event section shows the selected lanes of ledger data plus the action bar for lane-level actions and feedback.

### Lane behavior

- `Raw events` shows imported ledger events before corrections are applied.
- `Corrections` shows synthetic seed events and persisted spam markers.
- `Corrected events` shows the ledger after spam and seed corrections are applied.

### Supported actions

- Users can select one or more event cards and mark them as spam.
- Users can select one or more raw-backed event cards and create a replacement correction from those selected sources.
- Users can remove an existing spam marker from the `Corrections` lane.
- Users can remove an existing replacement correction from the `Corrections` lane.
- The date chooser scrolls the main timeline to the selected day.
- The column chooser controls which lanes are loaded and rendered.

## UI Structure

- `src/app/page.tsx` loads the selected columns, loads the merged accounts catalog from the backend, groups all loaded lane items by timestamp bucket, and wires the page-level providers.
- `src/components/Events/` owns event selection state, spam marker actions, and the action bar shown above the timeline. The directory keeps the React component in `Events.tsx`, selection state in `useEventSelection.ts`, and pure event-derivation helpers in `selectableEvents.ts`.
- `src/components/Events/ReplacementEditorModal.tsx` owns the structured replacement-creation form, including UTC timestamp editing and leg authoring.
- `src/components/VirtualizedDateSections.tsx` virtualizes timeline rows for rendering performance; all selected column data is still loaded in memory up front.
- `src/components/EventDateSection.tsx` renders one timestamp bucket across the currently selected columns.
- `src/components/LaneItem.tsx` dispatches each lane item to its visual component such as `EventCard`, `SeedCorrectionItem`, or `SpamCorrectionItem`.
- `src/components/EventCard.tsx` is the shared card UI for raw and corrected ledger events.
- `src/contexts/AccountNamesContext.tsx` exposes both the full merged account dataset and name-resolution helpers to client components.

## Architecture and Integration

### Communication with the backend

- The UI talks to FastAPI through the same-origin `/api/crypto-taxes/*` rewrite in `next.config.ts`.
- Put reusable API transport in `src/api/core.ts` and keep backend communication split into focused resource files under `src/api/` (ex. `events.ts`, `accounts.ts` etc.). Both server and client code should consume those shared API modules.
- `src/api/core.ts` owns the request/response case translation at the API boundary. Endpoint modules should expose camelCase TypeScript shapes and avoid duplicating snake_case DTO mirror types.

### API contract

- Base URL comes from `CRYPTO_TAXES_API_URL` (defaults to `http://localhost:8000`).
- Current endpoints:
  - `GET /raw-events`
  - `GET /seed-events`
  - `GET /corrected-events`
  - `GET /accounts` (merged wallet + system exchange accounts; `address` may be `null`)
  - `GET | POST | DELETE /replacement-corrections`
  - `GET | POST | DELETE /spam-corrections`

## Technical Workflow

### Tech stack

- Package manager is pnpm;
- Next.js 16 (React 19, TypeScript) app using the App Router; source code lives in `ui/src` with `@/*` aliasing to `src/*`.
- Runtime is a modern JS environment; feel free to use new ECMAScript features without downleveling or adding polyfills.
- Styling is Bootstrap 5, consumed through `react-bootstrap` (global import in `src/app/layout.tsx`); prefer `react-bootstrap` components and scoped styles (CSS modules or `globals.css`) for custom tweaks.
- Prettier 3 for formatting;
- ESLint is configured with Next core web vitals plus Prettier compatibility (`eslint.config.mjs`); keep new code aligned with those rules.

### Development commands

Don't run pnpm commands from Codex/LLM terminal sessions. In the current setup, UI command execution is unreliable there.
