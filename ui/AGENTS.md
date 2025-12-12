# UI Guidelines

- Next.js 16 (React 19, TypeScript) app using the App Router; source lives in `ui/src` with `@/*` aliasing to `src/*`.
- Styling is Bootstrap 5, consumed through `react-bootstrap` (global import in `src/app/layout.tsx`); prefer `react-bootstrap` components and scoped styles (CSS modules or `globals.css`) for custom tweaks.
- Formatting uses Prettier 3; run `pnpm prettier` before committing UI changes.
- Package manager is pnpm; primary scripts are `pnpm dev`, `pnpm build`, `pnpm start`, and `pnpm lint`.
- ESLint is configured with Next core web vitals plus Prettier compatibility (`eslint.config.mjs`); keep new code aligned with those rules.
- Data access uses Drizzle ORM against the shared SQLite DB (`crypto_taxes.db`); reuse helpers under `src/db/` for queries/migrations and avoid bypassing them.
