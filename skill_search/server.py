"""
MCP Server for Skill Search.

Universal skill search tool. Exposes three tools:
  - skill_search(query) — grep-like search, returns skill name + description
  - skill_view(name) — load full skill content
  - skill_list() — list all skills
"""

import os
import sys
import json
import asyncio
from typing import Optional

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp import types
except ImportError:
    print(
        "Error: 'mcp' package not installed.\n"
        "Install with: pip install 'mcp[cli]'",
        file=sys.stderr,
    )
    sys.exit(1)

from .engine import build_index, SkillIndex


# ── Config ──────────────────────────────────────────────────────────────────

DEFAULT_CATALOG = "~/.agents/skills-catalog"
LOCAL_CATALOG = "./.agents/skills-catalog"


def get_catalog_dirs() -> list[str]:
    """Resolve catalog directories from env or defaults."""
    env = os.environ.get("SKILL_CATALOG_DIRS", "")
    if env:
        dirs = [d.strip() for d in env.split(":") if d.strip()]
    else:
        dirs = []
        for d in [DEFAULT_CATALOG, LOCAL_CATALOG]:
            expanded = os.path.expanduser(d)
            if os.path.isdir(expanded):
                dirs.append(expanded)
    return dirs


# ── Server ──────────────────────────────────────────────────────────────────

app = Server("skill-search")
_index: Optional[SkillIndex] = None


def get_index() -> SkillIndex:
    global _index
    if _index is None:
        dirs = get_catalog_dirs()
        _index = build_index(*dirs)
    return _index


# ── Tool definitions ────────────────────────────────────────────────────────

TOOL_DEFINITIONS = [
    types.Tool(
        name="skill_search",
        description=(
            "Universal skill search tool. Use grep-like search terms to find relevant "
            "skills for your task. Always use this tool before writing code or executing "
            "tasks — there may be a skill that covers your exact use case. Returns skill "
            "names and descriptions only. Use skill_view to load full content."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Grep-style search terms (e.g. 'react performance', 'kubernetes deploy', 'api design')",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default 10)",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    ),
    types.Tool(
        name="skill_view",
        description=(
            "Load the full content of a skill by name. "
            "Use skill_search first to find relevant skills, then skill_view to read the one you need."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Exact skill name (from skill_search results)",
                },
            },
            "required": ["name"],
        },
    ),
    types.Tool(
        name="skill_list",
        description=(
            "List all skills in the catalog with name and description. "
            "Use skill_search for targeted queries."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max results (default 100)",
                    "default": 100,
                },
            },
        },
    ),
]


# ── Handlers ────────────────────────────────────────────────────────────────

async def handle_list_tools(
    request,
) -> types.ListToolsResult:
    return types.ListToolsResult(tools=TOOL_DEFINITIONS)


async def handle_call_tool(
    request,
) -> types.CallToolResult:
    params = request.params
    name = params.name
    arguments = params.arguments or {}
    index = get_index()

    if name == "skill_search":
        query = arguments.get("query", "")
        limit = arguments.get("limit", 10)
        results = index.search(query, limit=limit)
        # Return only name + description (lean output)
        lean = [{"name": r["name"], "description": r["description"]} for r in results]
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(lean, indent=2))],
            isError=False,
        )

    elif name == "skill_view":
        skill_name = arguments.get("name", "")
        result = index.get_skill(skill_name)
        if result:
            return types.CallToolResult(
                content=[types.TextContent(
                    type="text",
                    text=f"# {result['name']}\n\n{result['content']}",
                )],
                isError=False,
            )
        else:
            results = index.search(skill_name, limit=1)
            if results:
                return types.CallToolResult(
                    content=[types.TextContent(
                        type="text",
                        text=f"Skill '{skill_name}' not found. Did you mean '{results[0]['name']}'?",
                    )],
                    isError=False,
                )
            return types.CallToolResult(
                content=[types.TextContent(
                    type="text",
                    text=f"Skill '{skill_name}' not found in catalog.",
                )],
                isError=True,
            )

    elif name == "skill_list":
        limit = arguments.get("limit", 100)
        results = index.list_all(limit=limit)
        lean = [{"name": r["name"], "description": r["description"]} for r in results]
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(lean, indent=2))],
            isError=False,
        )

    return types.CallToolResult(
        content=[types.TextContent(type="text", text=f"Unknown tool: {name}")],
        isError=True,
    )


# Register handlers
app.add_request_handler("tools/list", types.PaginatedRequestParams, handle_list_tools)
app.add_request_handler("tools/call", types.CallToolRequestParams, handle_call_tool)


# ── Entry point ─────────────────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def run():
    asyncio.run(main())


if __name__ == "__main__":
    run()
