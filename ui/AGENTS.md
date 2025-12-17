# UI Guidelines

## Tech stack

- Package manager is pnpm;
- Next.js 16 (React 19, TypeScript) app using the App Router; source lives in `ui/src` with `@/*` aliasing to `src/*`.
- Styling is Bootstrap 5, consumed through `react-bootstrap` (global import in `src/app/layout.tsx`); prefer `react-bootstrap` components and scoped styles (CSS modules or `globals.css`) for custom tweaks.
- Prettier 3 for formatting;
- ESLint is configured with Next core web vitals plus Prettier compatibility (`eslint.config.mjs`); keep new code aligned with those rules.
- Data access uses Drizzle ORM against the shared SQLite DB (`crypto_taxes.db`); reuse helpers under `src/db/` for queries/migrations and avoid bypassing them.

## Database (read-only contract)

- The UI reads from the shared SQLite DB `../crypto_taxes.db` via Drizzle.
- Source of truth for the schema is the Python `data/` component (SQLAlchemy models). Treat UI DB code as one-way: align to the existing DB rather than introducing schema changes from the UI side.
- Drizzle schema should be generated/updated from the existing database state; avoid “designing” tables/columns in `ui/` first.

## Development commands

Don't run pnpm commands on your own. Currently, dev env is not configured correctly.
