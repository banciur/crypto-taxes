.PHONY: code_check code_fix help deps dev lint_check lint_fix test types

help:  ## prints help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ": .*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

code_check: lint_check types ## check linting, formatting and types

code_fix: lint_fix types ## lint and format the code

deps: ## install dependencies
	pip install .
	pip install .[dev]

lint_check: ## code quality tools: format, lint
	ruff check --select I
	ruff format --check

lint_fix: ## code quality tools: format, lint
	ruff check --select I --fix
	ruff format

test: ## run tests
	pytest -s

types: ## check typings
	mypy src tests