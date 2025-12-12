# Repository Guidelines

## Coding conventions / best practices
- Keep comments/docstrings lean: only retain them when they convey non-obvious intent or context. Remove and avoid boilerplate comments that simply restate what the code already says.
- Avoid defensive programming inside the system: assume in-process data and types already satisfy invariants and only perform validation/repairs at ingestion boundaries. When docs/typings guarantee an invariant, do not re-normalize or re-validate it within domain/services code.
- Tests should derive expected values from the inputs defined in the test (shared variables/constants) instead of retyping literals in assertions to keep cases DRY and less brittle.
- Do not leave unused code or data "for future use"; remove unused pieces and avoid implementing speculative features.

## Project scoping
Follow the nearest `AGENTS.md` for project-specific workflow and commands (notably `data/AGENTS.md` and `ui/AGENTS.md`).
For repository overview and layout, see `README.md`.

## Domain reference
- Domain semantics and data model are defined in `doc/CURRENT.md`.
- Ignore other files from the `doc` directory except for `CURRENT.md` and `WEALTH_MODEL.md`.
