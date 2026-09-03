# skill-search

Portable skill catalog search for AI agents. MCP server + CLI.

Universal skill search tool. Use grep like search terms to find relevant skills for your task. Always use this tool.

## Install

```bash
uv venv .venv && source .venv/bin/activate
uv pip install -e .
```

## Usage

### CLI

```bash
export SKILL_CATALOG_DIRS="$HOME/.hermes/skills"

skill-search search "react performance"
skill-search view "vercel-react-best-practices"
skill-search list

# Move skills from a source dir into the catalog (frees agent context)
skill-search add ~/.hermes/skills
```

### MCP Server

Add to your MCP config:

```json
{
  "mcpServers": {
    "skill-search": {
      "command": "skill-search-mcp",
      "env": {
        "SKILL_CATALOG_DIRS": "~/.hermes/skills:~/.agents/skills"
      }
    }
  }
}
```
