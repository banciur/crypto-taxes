# UI Guidelines

## Tech stack

- Package manager is pnpm;
- Next.js 16 (React 19, TypeScript) app using the App Router; source code lives in `ui/src` with `@/*` aliasing to `src/*`.
- Runtime is a modern JS environment; feel free to use new ECMAScript features without downleveling or adding polyfills.
- Styling is Bootstrap 5, consumed through `react-bootstrap` (global import in `src/app/layout.tsx`); prefer `react-bootstrap` components and scoped styles (CSS modules or `globals.css`) for custom tweaks.
- Prettier 3 for formatting;
- ESLint is configured with Next core web vitals plus Prettier compatibility (`eslint.config.mjs`); keep new code aligned with those rules.

## Architecture

### Communication with the backend

- The UI talks to FastAPI through the same-origin `/api/crypto-taxes/*` rewrite in `next.config.ts`.
- Put reusable API transport in `src/api/core.ts` and keep backend communication split into focused resource files under `src/api/` (ex. `events.ts`, `accounts.ts` etc.). Both server and client code should consume those shared API modules.
- `src/api/core.ts` owns the request/response case translation at the API boundary. Endpoint modules should expose camelCase TypeScript shapes and avoid duplicating snake_case DTO mirror types.

## API contract

- Base URL comes from `CRYPTO_TAXES_API_URL` (defaults to `http://localhost:8000`).
- Current endpoints:
  - `GET /raw-events`
  - `GET /seed-events`
  - `GET /corrected-events`
  - `GET /accounts`
  - `GET | POST | DELETE /spam-corrections`

## Development commands

Don't run pnpm commands from Codex/LLM terminal sessions. In the current setup, UI command execution is unreliable there.
