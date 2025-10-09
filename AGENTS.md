# Repository Guidelines

## Development commands
- `make deps` syncs the project and `dev` dependency groups into the local `.venv` via uv.
- `make code_check` runs `ruff check`, `ruff format --check`, and `mypy` to gate linting and types.
- `make code_fix` executes `ruff check --fix`, `ruff format`, and `mypy` to auto-fix linting and re-run types.
- `make test` runs the pytest suite (`uv run --group dev pytest -s`).

## Suggested workflow
- After making code changes run `make code_fix` to auto-apply lint fixes.
- Follow up with `make test` to ensure the suite passes before committing.
