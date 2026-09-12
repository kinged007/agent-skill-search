"""
Registry of agent clients the MCP server can be installed into.

Two adapter kinds:
- command-backed: run the client's own `mcp add` (its config is TOML/YAML or
  actively managed; the client binary stays the schema authority)
- file-backed: merge the server entry into the client's JSON config

Pure data plus path resolution — all I/O lives in install.py.
"""

import os
import sys
from dataclasses import dataclass, field

SERVER_NAME = "skill-search"


@dataclass(frozen=True)
class Client:
    id: str
    name: str
    binary: str | None = None            # command-backed: binary that must be on PATH
    add_args: tuple[str, ...] | None = None   # argv template; {cmd} and {env} tokens
    remove_args: tuple[str, ...] | None = None
    config_paths: tuple[str, ...] = ()   # file-backed: home-relative candidates ("APPDATA:" prefix = %APPDATA%-rooted)
    json_key: tuple[str, ...] = ()       # key path to the servers dict
    use_cwd: bool = False                # legacy: config was project-root-relative
    note: str = ""


CLIENTS: list[Client] = [
    Client(
        id="claude-code", name="Claude Code", binary="claude",
        add_args=("mcp", "add", "--scope", "user", "-e", "{env}", "--", SERVER_NAME, "{cmd}"),
        remove_args=("mcp", "remove", "-s", "user", SERVER_NAME),
    ),
    Client(
        id="codex", name="Codex CLI", binary="codex",
        add_args=("mcp", "add", SERVER_NAME, "--env", "{env}", "--", "{cmd}"),
        remove_args=("mcp", "remove", SERVER_NAME),
    ),
    Client(
        id="openclaw", name="OpenClaw", binary="openclaw",
        add_args=("mcp", "add", "-e", "{env}", SERVER_NAME, "--", "{cmd}"),
        remove_args=("mcp", "remove", SERVER_NAME),
    ),
    Client(
        id="hermes", name="Hermes", binary="hermes",
        add_args=("mcp", "add", "-e", "{env}", SERVER_NAME, "--", "{cmd}"),
        remove_args=("mcp", "remove", SERVER_NAME),
    ),
    Client(
        id="opencode", name="opencode",
        config_paths=(".config/opencode/opencode.json", ".config/opencode/opencode.jsonc"),
        json_key=("mcp",),
        note="config is JSONC; installer refuses to rewrite files with comments",
    ),
    Client(
        id="gemini", name="Gemini CLI",
        config_paths=(".gemini/settings.json",),
        json_key=("mcpServers",),
    ),
    Client(
        id="claude-desktop", name="Claude Desktop",
        config_paths=(
            "darwin:Library/Application Support/Claude/claude_desktop_config.json",
            "win32:APPDATA:Claude/claude_desktop_config.json",
        ),
        json_key=("mcpServers",),
        note="macOS/Windows only — no official Linux build",
    ),
    Client(
        id="pi", name="pi",
        config_paths=("~/.pi/agent/mcp.json",),
        json_key=("mcpServers",),
        note="pi has no built-in MCP; needs the pi-mcp extension loaded",
    ),
    Client(
        id="chatgpt", name="ChatGPT",
        note="remote HTTPS connector only — run the server with --http",
    ),
]


def get_client(client_id: str) -> Client | None:
    return next((c for c in CLIENTS if c.id == client_id), None)


def resolve_config_path(client: Client) -> str | None:
    """First applicable candidate whose parent dir exists; else first applicable; None if no paths.

    Candidate prefixes: "darwin:"/"win32:"/"linux:" restrict to a platform;
    "APPDATA:" roots the remainder at %APPDATA%. Untagged paths are home- (or
    cwd-) relative.
    """
    first = None
    for raw in client.config_paths:
        path = raw
        tag, sep, rest = raw.partition(":")
        if sep and tag in ("darwin", "win32", "linux"):
            if sys.platform != tag:
                continue
            path = rest
        if path.startswith("APPDATA:"):
            appdata = os.environ.get("APPDATA")
            if not appdata:
                continue
            path = os.path.join(appdata, path[len("APPDATA:"):])
        elif path.startswith("~"):
            path = os.path.expanduser(path)
        else:
            path = os.path.join(os.path.expanduser("~"), path)
        if first is None:
            first = path
        if os.path.isdir(os.path.dirname(path) or "."):
            return path
    return first
