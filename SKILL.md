---
name: skill-search
description: "Universal skill search tool. Use grep like search terms to find relevant skills for your task. Always use this tool."
---

# Skill Search

A portable tool that lets agents search through a catalog of SKILL.md files and load only the relevant ones — instead of dumping 100+ skills into context.

## How It Works

The tool has two modes:

1. **MCP Server** — for Claude Code, Claude Desktop, Codex, Gemini CLI, OpenClaw, Hermes, pi, or any MCP-capable agent. Exposes `skill_search`, `skill_view`, and `skill_list` as tools.
2. **CLI** — for any agent. Run `skill-search search <query>` to find skills, `skill-search view <name>` to load one.

## Setup

Install the package first (distribution name is `agent-skill-search`):

```bash
uv tool install agent-skill-search
# or: pip install agent-skill-search
```

### Option A: MCP Server (recommended)

One command per client:

```bash
skill-search install claude-code   # or codex / gemini / openclaw / hermes / pi / claude-desktop
```

Manual fallback for any `mcpServers`-style JSON config:

```json
{
  "mcpServers": {
    "skill-search": {
      "command": "/absolute/path/to/skill-search-mcp",
      "args": [],
      "env": {
        "SKILL_CATALOG_DIRS": "/path/to/your/skills:/path/to/more/skills"
      }
    }
  }
}
```

Or with `uvx` (note the `--from`, since the distribution is `agent-skill-search`):

```json
{
  "mcpServers": {
    "skill-search": {
      "command": "uvx",
      "args": ["--from", "agent-skill-search", "skill-search-mcp"],
      "env": {
        "SKILL_CATALOG_DIRS": "~/.hermes/skills:~/.agents/skills"
      }
    }
  }
}
```

Full per-client instructions, the ChatGPT remote-HTTP setup, and troubleshooting:
**[INSTALL.md](INSTALL.md)**.

### Option B: CLI (any agent)

```bash
pip install agent-skill-search

# Set your catalog directories (colon-separated)
export SKILL_CATALOG_DIRS="$HOME/.hermes/skills:$HOME/.agents/skills"

# Search
skill-search search "react performance"

# View a skill
skill-search view "vercel-react-best-practices"

# List all
skill-search list
```

### Option C: Local development

```bash
cd skill-search
pip install -e .
export SKILL_CATALOG_DIRS="."
skill-search list
```

## Catalog management

`skill-search add <dir>` **moves** skill directories out of the source tree into
`~/.agents/skills-catalog` — it does not copy them. The originals will no longer be in
place for the tool they came from.

## Usage Pattern for Agents

1. **Discover** — run `skill_search(query="your topic")` to find matching skills
2. **Evaluate** — read the name + description from results
3. **Load** — run `skill_view(name="the-skill")` to get full instructions
4. **Execute** — follow the skill's procedure

This keeps context lean: only the catalog index (~3k tokens) plus the one skill you actually need.

## Catalog Structure

Point the tool at directories containing SKILL.md files:

```
your-catalog/
├── react-performance/
│   └── SKILL.md
├── kubernetes-deploy/
│   └── SKILL.md
└── api-design/
    └── SKILL.md
```

Any directory tree containing SKILL.md files works — the tool scans recursively.
