# UI Guidelines

## Tech stack

- Package manager is pnpm;
- Next.js 16 (React 19, TypeScript) app using the App Router; source code lives in `ui/src` with `@/*` aliasing to `src/*`.
- Runtime is a modern JS environment; feel free to use new ECMAScript features without downleveling.
- Styling is Bootstrap 5, consumed through `react-bootstrap` (global import in `src/app/layout.tsx`); prefer `react-bootstrap` components and scoped styles (CSS modules or `globals.css`) for custom tweaks.
- Prettier 3 for formatting;
- ESLint is configured with Next core web vitals plus Prettier compatibility (`eslint.config.mjs`); keep new code aligned with those rules.
- Data access goes through the FastAPI service in `data/src/api/`; fetch helpers under `src/api/`

## API contract

- Base URL comes from `CRYPTO_TAXES_API_URL` (defaults to `http://localhost:8000`).
- Current endpoints:
  - `GET /raw-events`
  - `GET /seed-events`
  - `GET /corrected-events`

## Development commands

Don't run pnpm commands on your own. Currently, dev env is not configured correctly.
