# AGENTS.md — agent-skill-search

## Purpose

Portable skill catalog search for AI agents. CLI (`skill-search`) + MCP server (`skill-search-mcp`, tools: `skill_search`, `skill_view`, `skill_list`). Skills are stored as `SKILL.md` files in a catalog indexed with SQLite FTS5.

## How to work in this repo

- Python 3.10+, package `agent-skill-search`, entry points `skill_search.cli:main` and `skill_search.server:run`.
- Install dev deps: `pip install ".[dev]" ruff mypy`.
- Checks (same as CI):
  ```
  pytest -q
  ruff check .
  mypy skill_search --ignore-missing-imports
  ```
- Catalog for tests is `test-catalog/`; set `SKILL_CATALOG_DIRS` to point at it when exercising CLI/server locally.
- `skill_search/engine.py` owns indexing/search, `cli.py` the CLI, `server.py` the MCP server, `install.py`/`clients.py` per-client install adapters.

## Using skills in this repo

Prefer the `skill-search` MCP tools or CLI over reading every `SKILL.md` into context. Example:

```bash
skill-search search "mcp|install"
skill-search view "skill-search"
```

The catalog dir defaults to `~/.agents/skills-catalog`; add local skills with `skill-search add <dir>`.

## Branch / PR workflow

- Do not push directly to `main`.
- Create a feature branch, commit, push, and open a PR against `main`.
- CI (`ci.yml`) runs `pytest` + `ruff` + `mypy` on Python 3.10 and 3.12 for every push/PR to `main`.

## Permissions

- Do not commit secrets (API keys, tokens, .env). Only .env.example belongs in the repo.
- This repo is self-contained. Do not add network calls in tests; mock external services.

## Commit authorship

Use `kinged007 <599286+kinged007@users.noreply.github.com>` for commits.
