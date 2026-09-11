# Agent Skill Search

Portable skill catalog search for AI agents. MCP server + CLI.

Skills folders eat your agent's context window — every SKILL.md loads whether the task needs it or not. Move them into a catalog and the agent fetches a skill only when it's relevant. Use grep-like search terms to find the right one for your task.

## Install

```bash
# recommended — isolated tool install
uv tool install agent-skill-search
# or
pip install agent-skill-search
```

> The PyPI distribution is **`agent-skill-search`** — the name `skill-search` on PyPI
> belongs to an unrelated package. The commands stay `skill-search` and `skill-search-mcp`.

## Usage

### CLI

```bash
export SKILL_CATALOG_DIRS="$HOME/.hermes/skills"

skill-search search "react performance"
skill-search view "vercel-react-best-practices"
skill-search list

# Also scan well-known agent skills dirs (opencode, claude, codex, ...).
# Same-named skills are deduplicated; off by default.
skill-search --include-known list        # or SKILL_INCLUDE_KNOWN=1

# Move skills from a source dir into the catalog (frees agent context).
# Note: `add` MOVES directories out of the source tree, it does not copy.
skill-search add ~/.hermes/skills
```

### MCP server

One command installs it into your client:

```bash
skill-search install claude-code   # or codex / gemini / openclaw / hermes / pi / claude-desktop / chatgpt
```

See **[INSTALL.md](INSTALL.md)** for per-client details, manual config snippets, the
ChatGPT remote-HTTP setup, and troubleshooting.

Agents without an MCP connection can use the CLI directly. Opt in to append a
short usage snippet to existing `CLAUDE.md`/`AGENTS.md` files (marker-checked,
append-only, never created from scratch):

```bash
skill-search install gemini --cli-hint
```

## License

MIT — see [LICENSE](LICENSE).
