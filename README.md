# crypto-taxes
Yet another unfinished system for tracking crypto transactions and calculating taxes. But I need something tailored for a stable farmer in Germany.

## Docs
- Current domain model: `doc/CURRENT.md`
- Developer/agent workflow: `AGENTS.md`

## Quickstart
Project uses [uv](https://docs.astral.sh/uv/) with Python 3.13.

- Setup: `make deps`
- Run tests: `make test`
- Code quality: `make code_fix` (autofix) or `make code_check` (lint+types)
