# Agent Skill Search

[![CI](https://github.com/kinged007/agent-skill-search/actions/workflows/ci.yml/badge.svg)](https://github.com/kinged007/agent-skill-search/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/agent-skill-search)](https://pypi.org/project/agent-skill-search/)
[![Python 3.10+](https://img.shields.io/pypi/pyversions/agent-skill-search)](https://pypi.org/project/agent-skill-search/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Portable skill catalog search for AI agents. MCP server + CLI so agents fetch skills only when relevant instead of loading every `SKILL.md` into the context window.

Skills folders eat your agent's context window — every `SKILL.md` loads whether the task needs it or not. Move them into a catalog and the agent fetches a skill only when it is relevant. Search with grep-like terms to find the right skill for the task.

## Install

```bash
# recommended — isolated tool install
uv tool install agent-skill-search
# or
pip install agent-skill-search
```

> The PyPI distribution is **`agent-skill-search`** — the name `skill-search` on PyPI belongs to an unrelated package. The commands stay `skill-search` and `skill-search-mcp`.

## Usage

### CLI

```bash
skill-search --version               # show version
skill-search update                  # upgrade to the latest release
skill-search update --check          # show current version only

# Shorthand: `skill-search "<query>"` == `skill-search search "<query>"`.
skill-search "react performance"

# Default catalog dir is `~/.agents/skills-catalog` (persist a custom one with
# `skill-search dirs --set DIR`). Override per command with `--dirs` or
# `SKILL_CATALOG_DIRS=dir1:dir2`. Bare `skill-search` prints help plus the
# active dirs.

export SKILL_CATALOG_DIRS="$HOME/.hermes/skills"

skill-search search "react performance"
skill-search search "planning|prd|guide"   # multiple keywords (OR search)
skill-search view "vercel-react-best-practices"
skill-search list

# Also scan well-known agent skills dirs (opencode, claude, codex, ...).
# Same-named skills are deduplicated; off by default.
skill-search --include-known list        # or SKILL_INCLUDE_KNOWN=1

# `add` COPIES skill dirs into the default catalog (`~/.agents/skills-catalog`
# unless changed with `dirs --set`); the source tree is left untouched.
skill-search add ~/.hermes/skills

# Always shows the active dirs (stderr); inspect or change the default:
skill-search dirs                # show default, config file, known dirs, active dirs
skill-search dirs --set ~/skills # persist DIR as the default catalog
skill-search dirs --reset        # back to ~/.agents/skills-catalog (also: `dirs --set ""`)
```

### MCP server

One command installs it into your client:

```bash
skill-search install claude-code   # or opencode / codex / gemini / openclaw / hermes / pi / claude-desktop / chatgpt
```

See **[INSTALL.md](INSTALL.md)** for per-client details, manual config snippets, the ChatGPT remote-HTTP setup, and troubleshooting.

Agents without an MCP connection can use the CLI directly. Opt in to append a short usage snippet to existing `CLAUDE.md`/`AGENTS.md` files (marker-checked, append-only, never created from scratch):

```bash
skill-search install gemini --cli-hint
```

## How it is tested

```bash
pip install ".[dev]"
pip install ruff mypy
pytest -q
ruff check .
mypy skill_search
```

- `tests/test_dirs.py` — catalog resolution and config persistence.
- `tests/test_install.py` — client install adapters.
- `tests/test_server_smoke.py` — end-to-end MCP stdio and HTTP round-trips against `test-catalog/`.

CI runs the same checks on every push and PR to `main` (Python 3.10 and 3.12): `pytest`, `ruff check`, and `mypy`.

## License

MIT — see [LICENSE](LICENSE).
