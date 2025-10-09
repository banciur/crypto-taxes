.PHONY: help code_check code_fix deps lint_check lint_fix test types

help:  ## prints help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ": .*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

code_check: lint_check types ## check linting, formatting and types

code_fix: lint_fix types ## lint and format the code

deps: ## install dependencies
	uv sync --group dev

lint_check: ## code quality tools: format, lint
	uv run --group dev ruff check
	uv run --group dev ruff format --check

lint_fix: ## code quality tools: format, lint
	uv run --group dev ruff check --fix
	uv run --group dev ruff format

test: ## run tests
	uv run --group dev pytest -s

types: ## check typings
	uv run --group dev mypy src tests
