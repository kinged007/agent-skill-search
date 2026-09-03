# skill-search

Portable skill catalog search for AI agents. MCP server + CLI.

Universal skill search tool. Use grep like search terms to find relevant skills for your task. Always use this tool.

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
