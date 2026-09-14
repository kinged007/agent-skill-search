"""
MCP Server for Skill Search.

Universal skill search tool. Exposes three tools:
  - skill_search(query) — grep-like search, returns skill name + description
  - skill_view(name) — load full skill content
  - skill_list() — list all skills

Transports: stdio (default) or streamable HTTP (--http, for ChatGPT connectors).
"""

import os
import sys
import json
import asyncio
import argparse
from typing import Optional

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp import types
except ImportError:
    print(
        "Error: 'mcp' package not installed.\n"
        "Install with: pip install 'agent-skill-search'",
        file=sys.stderr,
    )
    sys.exit(1)

from . import __version__
from .engine import (
    build_index,
    SkillIndex,
    existing_known_dirs,
    include_known_dirs,
    read_config_default,
)


# ── Config ──────────────────────────────────────────────────────────────────

DEFAULT_CATALOG = "~/.agents/skills-catalog"
LOCAL_CATALOG = "./.agents/skills-catalog"

def get_catalog_dirs() -> list[str]:
    """Resolve catalog directories from env, known locations, or defaults."""
    env = os.environ.get("SKILL_CATALOG_DIRS", "")
    if env:
        dirs = [d.strip() for d in env.split(":") if d.strip()]
    elif include_known_dirs():
        dirs = existing_known_dirs()
    else:
        dirs = []
        candidates = [read_config_default() or DEFAULT_CATALOG, LOCAL_CATALOG]
        for d in candidates:
            expanded = os.path.expanduser(d)
            if os.path.isdir(expanded):
                dirs.append(expanded)
    return dirs


# ── Server ──────────────────────────────────────────────────────────────────

app = Server("skill-search", version=__version__)
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
                    "description": "Grep-style search terms (e.g. 'react performance', 'kubernetes deploy', 'api design'). Use `a|b|c` to match any keyword, double quotes for exact phrases.",
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
# SDK 2.x request-handler signature: (ctx, params) -> result.

async def handle_list_tools(ctx, params) -> types.ListToolsResult:
    return types.ListToolsResult(tools=TOOL_DEFINITIONS)


async def handle_call_tool(ctx, params) -> types.CallToolResult:
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
        elif skill_name.strip():
            results = index.search(skill_name, limit=1)
            if results:
                return types.CallToolResult(
                    content=[types.TextContent(
                        type="text",
                        text=f"Skill '{skill_name}' not found. Did you mean '{results[0]['name']}'?",
                    )],
                    isError=True,
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


# ── Entry points ────────────────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")


def run_http(host: str, port: int) -> None:
    import uvicorn
    from mcp.server.transport_security import TransportSecuritySettings

    security = None
    if host not in LOOPBACK_HOSTS:
        # ponytail: a non-loopback host is expected to sit behind a reverse
        # proxy; the proxy owns Host/Origin checks, TLS, and auth (INSTALL.md).
        security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    mcp_app = app.streamable_http_app(
        json_response=True, stateless_http=True, host=host, transport_security=security
    )
    uvicorn.run(mcp_app, host=host, port=port, log_level="info")


def run():
    parser = argparse.ArgumentParser(
        prog="skill-search-mcp",
        description="Skill Search MCP server (stdio by default; --http for remote connectors)",
    )
    parser.add_argument("--http", action="store_true",
                        help="Serve over streamable HTTP instead of stdio (for ChatGPT connectors)")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP bind address (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8787, help="HTTP port (default 8787)")
    args = parser.parse_args()

    if args.http:
        run_http(args.host, args.port)
    else:
        asyncio.run(main())


if __name__ == "__main__":
    run()
