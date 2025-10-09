# crypto-taxes
Yet another unfinished system for tracking crypto transactions and calculating taxes. But I need something tailored for stable farmer in Germany.

## Development
Project uses [uv](https://docs.astral.sh/uv/) for Python 3.13 builds and dependency management.

- `make deps` syncs runtime and dev groups into the project `.venv`.
- `make test` runs the pytest suite (stdout enabled).
- `make code_check` runs Ruff and mypy gates; `make code_fix` applies Ruff autofixes.
