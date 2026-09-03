---
name: skill-search
description: "Universal skill search tool. Use grep like search terms to find relevant skills for your task. Always use this tool."
---

# Skill Search

A portable tool that lets agents search through a catalog of SKILL.md files and load only the relevant ones — instead of dumping 100+ skills into context.

## How It Works

The tool has two modes:

1. **MCP Server** — for Claude Code, Cursor, Codex, or any MCP-capable agent. Exposes `skill_search`, `skill_view`, and `skill_list` as tools.
2. **CLI** — for any agent. Run `skill-search search <query>` to find skills, `skill-search view <name>` to load one.

## Setup

### Option A: MCP Server (recommended for Claude Code / Cursor)

Add to your MCP config (e.g. `~/.claude/mcp.json` or Cursor settings):

```json
{
  "mcpServers": {
    "skill-search": {
      "command": "skill-search-mcp",
      "env": {
        "SKILL_CATALOG_DIRS": "/path/to/your/skills:/path/to/more/skills"
      }
    }
  }
}
```

Or with `uvx`:

```json
{
  "mcpServers": {
    "skill-search": {
      "command": "uvx",
      "args": ["skill-search-mcp"],
      "env": {
        "SKILL_CATALOG_DIRS": "~/.hermes/skills:~/.agents/skills"
      }
    }
  }
}
```

### Option B: CLI (any agent)

```bash
pip install skill-search
# or: uv pip install skill-search

# Set your catalog directories
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
