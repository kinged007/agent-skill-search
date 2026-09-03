# Installing skill-search into agent clients

`skill-search` ships an MCP server (`skill-search-mcp`) and a CLI (`skill-search`). Every
major agent client can use it; the right channel depends on what the client supports:

| Client | Channel | What `install` does |
| --- | --- | --- |
| Claude Code | stdio MCP | runs `claude mcp add --scope user` |
| Codex CLI | stdio MCP | runs `codex mcp add` |
| OpenClaw | stdio MCP | runs `openclaw mcp add` |
| Hermes | stdio MCP | runs `hermes mcp add` |
| Gemini CLI | stdio MCP | merges `~/.gemini/settings.json` |
| Claude Desktop | stdio MCP | merges `claude_desktop_config.json` |
| pi | stdio MCP | merges `./mcp.json` (needs the `pi-mcp` extension) |
| ChatGPT | remote HTTPS MCP | prints self-host instructions (no local config) |
| Anything else | CLI from a SKILL.md | nothing to install — see below |

## 1. Install the package

Python 3.10+ required.

```bash
# recommended — isolated tool install, no environment conflicts
uv tool install agent-skill-search
# or
pipx install agent-skill-search
# or, into the current environment
pip install agent-skill-search
```

This gives you:

- `skill-search` — the CLI (`search`, `view`, `list`, `add`, `install`, `uninstall`)
- `skill-search-mcp` — the MCP server binary

> **Name collision warning:** an unrelated PyPI package named `skill-search` also installs
> a `skill-search` command. This project's distribution is **`agent-skill-search`**. If both
> end up in one environment, whichever was installed last owns the command — prefer
> `uv tool install` / `pipx`, which isolate each tool.

## 2. Prepare a catalog (optional)

The server reads SKILL.md catalogs from, in order:

1. `SKILL_CATALOG_DIRS` (colon-separated, e.g. `~/skills:~/more-skills`)
2. `~/.agents/skills-catalog` (default; created on demand)
3. `./.agents/skills-catalog` (project-local default)

`skill-search install` writes the resolved catalog dirs into each client's config as
`SKILL_CATALOG_DIRS`, so the client does not need the env var set. Override per install:

```bash
skill-search install gemini --catalog ~/my-skills --catalog ~/team-skills
```

## 3. Install into clients

Run `skill-search install --list` for the registry, then per client:

### Claude Code

```bash
skill-search install claude-code            # claude mcp add --scope user
skill-search install claude-code --dry-run  # print the command, write nothing
```

Verify: `claude mcp list`, or `/mcp` inside a session.

### Codex CLI

```bash
skill-search install codex
```

Verify: `codex mcp list`, then start `codex` and confirm the `skill_search` tools.

If your Codex version's `mcp add` does not accept `-e KEY=VALUE`, remove the
`[mcp_servers.skill-search]` entry it may have half-written and add it by hand:

```toml
[mcp_servers.skill-search]
command = "/absolute/path/to/skill-search-mcp"
env = { "SKILL_CATALOG_DIRS" = "/path/to/catalog" }
```

### Gemini CLI

```bash
skill-search install gemini
```

Merges `mcpServers` into `~/.gemini/settings.json`, backs the file up first
(`settings.json.bak-1`), and refuses to touch a malformed file. Verify: run `gemini`
and use `/mcp`.

Manual fallback:

```json
{
  "mcpServers": {
    "skill-search": {
      "command": "/absolute/path/to/skill-search-mcp",
      "args": [],
      "env": { "SKILL_CATALOG_DIRS": "/path/to/catalog" }
    }
  }
}
```

### OpenClaw

```bash
skill-search install openclaw
```

Verify: `/mcp` in an OpenClaw session. If your OpenClaw version has no `mcp add`
command, add the entry under `mcp.servers` in `~/.openclaw/openclaw.json` by hand —
same shape as the Gemini snippet above, nested under `"mcp": {"servers": {...}}`.

### Hermes

```bash
skill-search install hermes
```

Hermes config is YAML, so the installer goes through `hermes mcp add` rather than
editing the file. Manual fallback: add a `skill-search` entry under `mcp_servers` in
`~/.hermes/config.yaml`.

### pi

```bash
skill-search install pi
```

Writes `mcp.json` in the **current project root**. Requires the
[`pi-mcp` extension](https://github.com/badlogic/pi-mcp) in that project. Verify:
restart pi and check the tool list.

### Claude Desktop

```bash
skill-search install claude-desktop
```

macOS/Windows only (there is no official Linux build). Merges `mcpServers` into:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Verify: fully quit and reopen Claude Desktop — the server appears under
Settings → Connectors / the tools icon. Logs: `~/Library/Logs/Claude/mcp*.log`
(macOS) or `%APPDATA%\Claude\logs` (Windows).

### ChatGPT (self-hosted connector)

ChatGPT cannot run local stdio MCP servers. It connects to remote HTTPS MCP
endpoints, so run this server in HTTP mode and expose it over TLS:

```bash
skill-search-mcp --http --host 127.0.0.1 --port 8787
# then terminate TLS and forward, e.g. with Caddy:
#   caddy reverse-proxy --from mcp.example.com --to 127.0.0.1:8787
```

In ChatGPT: **Settings → Apps & Connectors → enable Developer mode → Create**,
with Server URL `https://your-domain/mcp`.

Server flags: `--host` (default `127.0.0.1`), `--port` (default `8787`).

> **Warning:** the endpoint publishes the whole catalog, read-only, to anyone who can
> reach it. The server implements no auth — authentication and TLS are the reverse
> proxy's job. Keep it behind auth or a private network. Binding a non-loopback host
> disables the SDK's DNS-rebinding protection for exactly this reason.

### Any other agent (CLI fallback)

Agents that load `SKILL.md` skills but have no MCP support can shell out to the CLI.
Install the package, then drop this repo's `SKILL.md` into their skills directory and
point the agent at:

```bash
skill-search search "react performance"   # find skills
skill-search view "react-perf"            # load one
```

## Uninstall

```bash
skill-search uninstall claude-code    # claude mcp remove
skill-search uninstall gemini         # removes the JSON entry, keeps a backup
skill-search uninstall --all          # every detected client
```

## Troubleshooting

- **Server won't start in the client** — the config must reference an absolute path.
  The installer resolves `skill-search-mcp` on your `PATH` and writes the absolute
  location; if it wasn't found it writes `<python> -m skill_search.server` instead
  (printed at install time). Hand-edited configs must do the same.
- **No skills found** — `SKILL_CATALOG_DIRS` is colon-separated
  (`dir1:dir2`). Check what got written with `skill-search install <client> --dry-run`,
  and test locally with `SKILL_CATALOG_DIRS=... skill-search list`.
- **`skill-search` command belongs to another package** — see the collision warning
  above; use `uv tool install agent-skill-search` or `pipx`.
- **Claude Desktop logs** — `~/Library/Logs/Claude/mcp*.log` (macOS),
  `%APPDATA%\Claude\logs` (Windows).
- **`skill-search add` moves directories** — it moves skill dirs out of the source
  tree into `~/.agents/skills-catalog` (not a copy).
- **Client config schema drift** — command-backed clients (Claude Code, Codex,
  OpenClaw, Hermes) delegate to their own `mcp add`, so their vendor owns the schema.
  The file-backed targets (Gemini CLI, Claude Desktop, pi) are the ones that may need
  updates if their config format changes.
