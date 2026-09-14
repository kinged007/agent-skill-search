"""
`skill-search install <client>` — write the MCP server into agent client configs.

Command-backed clients are installed through their own `mcp add` binary so we
never hand-write their config format. File-backed clients get a JSON merge with
a backup taken before the first write. --dry-run prints and writes nothing.
"""

import os
import re
import sys
import json
import shutil
import subprocess
from dataclasses import dataclass

from . import clients as cl
from .engine import existing_known_dirs, include_known_dirs, read_config_default
from .clients import SERVER_NAME, CLIENTS, Client, get_client, resolve_config_path

DEFAULT_CATALOG = "~/.agents/skills-catalog"

def default_catalog_dir() -> str:
    """Builtin default, or the persisted custom default from `dirs --set`."""
    return read_config_default() or os.path.expanduser(DEFAULT_CATALOG)


# ── Resolution ──────────────────────────────────────────────────────────────

def resolve_catalog_dirs(explicit: list[str] | None, include_known: bool | None = None) -> list[str]:
    """--catalog (repeatable) > SKILL_CATALOG_DIRS env > ~/.agents/skills-catalog.

    --include-known/--no-include-known (else SKILL_INCLUDE_KNOWN=1) additionally
    scans well-known agent skills dirs. Dirs from --catalog or the default are
    created if missing; env-referenced and known dirs are not (other tools own
    them).
    """
    if include_known is None:
        include_known = include_known_dirs()
    if explicit:
        raw, create = list(explicit), True
    else:
        env = os.environ.get("SKILL_CATALOG_DIRS", "")
        raw = env.split(":") if env else [default_catalog_dir()]
        create = not env
    if include_known:
        raw = [*raw, *existing_known_dirs()]

    out, seen = [], set()
    for d in raw:
        d = d.strip()
        if not d:
            continue
        real = os.path.realpath(os.path.expanduser(d))
        if real not in seen:
            seen.add(real)
            out.append(real)
    if create:
        for d in out:
            os.makedirs(d, exist_ok=True)
    if not out:
        print(f"Error: no catalog directories resolved. "
              f"Pass --catalog DIR or set SKILL_CATALOG_DIRS.", file=sys.stderr)
        sys.exit(1)
    return out


def resolve_server_command() -> tuple[str, list[str]]:
    """Absolute command that runs the MCP server, independent of the client's PATH."""
    found = shutil.which("skill-search-mcp")
    if found:
        return found, []
    return sys.executable, ["-m", "skill_search.server"]


def server_entry(dirs: list[str], cmd: str, cmd_args: list[str]) -> dict:
    return {
        "command": cmd,
        "args": cmd_args,
        "env": {"SKILL_CATALOG_DIRS": ":".join(dirs)},
    }


# ── Targets ─────────────────────────────────────────────────────────────────

@dataclass
class Target:
    client: Client
    present: bool  # client looks installed


def select_targets(client_ids: list[str], all_clients: bool) -> list[Target]:
    if all_clients:
        chosen = [c for c in CLIENTS if c.id != "chatgpt" and not (c.use_cwd and all_clients)]
        targets = []
        for c in chosen:
            present = (
                shutil.which(c.binary) is not None if c.binary
                else (resolve_config_path(c) is not None
                      and os.path.isdir(os.path.dirname(resolve_config_path(c))))
            )
            if present:
                targets.append(Target(c, True))
            else:
                print(f"  skip {c.id}: not installed on this machine")
        return targets
    out = []
    for cid in client_ids:
        c = get_client(cid)
        if c is None:
            print(f"Error: unknown client '{cid}'. "
                  f"Known: {', '.join(c.id for c in CLIENTS)}", file=sys.stderr)
            sys.exit(1)
        out.append(Target(c, True))
    return out


# ── Install ─────────────────────────────────────────────────────────────────

def cmd_install(args) -> None:
    if args.list:
        list_clients()
        return

    if not args.all and not args.client:
        print("Error: pass a client id, --all, or --list. "
              "See `skill-search install --list`.", file=sys.stderr)
        sys.exit(1)

    client_ids = args.client or []
    targets = select_targets(client_ids, args.all)
    if not targets:
        print("Nothing to install.")
        return

    dirs = resolve_catalog_dirs(args.catalog, getattr(args, "include_known", None))
    if getattr(args, "cli_hint", False):
        append_cli_hint(args.dry_run)
    cmd, cmd_args = resolve_server_command()
    if not shutil.which("skill-search-mcp"):
        print("Note: 'skill-search-mcp' not on PATH; writing interpreter command "
              f"({cmd} {' '.join(cmd_args)}) instead.")

    failed = False
    for t in targets:
        try:
            if t.client.id == "chatgpt":
                print_chatgpt_instructions(dirs, args.dry_run)
            elif t.client.binary:
                install_command_backed(t, dirs, cmd, cmd_args, args.dry_run)
            elif t.client.id == "opencode":
                install_opencode(t, dirs, cmd, cmd_args, args.dry_run)
            else:
                install_file_backed(t, dirs, cmd, cmd_args, args.dry_run)
            print(f"  ok: {t.client.id}")
        except SystemExit:
            failed = True
    if failed:
        sys.exit(1)


def install_command_backed(t: Target, dirs, cmd, cmd_args, dry_run: bool) -> None:
    c = t.client
    argv = [c.binary]
    for token in c.add_args:
        if token == "{cmd}":
            argv.extend([cmd, *cmd_args])
        elif token == "{env}":
            argv.append("SKILL_CATALOG_DIRS=" + ":".join(dirs))
        else:
            argv.append(token)

    if not shutil.which(c.binary):
        print(f"Error: '{c.binary}' not found on PATH — install {c.name} first.",
              file=sys.stderr)
        sys.exit(1)

    if dry_run:
        print(f"[dry-run] {c.id}:")
        print("  $ " + " ".join(argv))
        return

    print(f"{c.id}: $ {' '.join(argv)}")
    result = subprocess.run(argv)
    if result.returncode != 0:
        print(f"Error: {' '.join(argv[:2])} exited with code {result.returncode}.",
              file=sys.stderr)
        sys.exit(1)


def install_file_backed(t: Target, dirs, cmd, cmd_args, dry_run: bool) -> None:
    c = t.client
    path = resolve_config_path(c)
    if path is None:
        print(f"Error: could not resolve config path for {c.name}.", file=sys.stderr)
        sys.exit(1)

    if dry_run:
        print(f"[dry-run] {c.id}: would write {path}")
        print("  " + json.dumps(server_entry(dirs, cmd, cmd_args)))
        return

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    data = {}
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error: {path} is not valid JSON ({e}); refusing to overwrite. "
                  f"Fix or remove the file, then retry.", file=sys.stderr)
            sys.exit(1)

    node = data
    for key in c.json_key[:-1]:
        node = node.setdefault(key, {})
    entry = server_entry(dirs, cmd, cmd_args)
    leaf = c.json_key[-1]
    existing = node.setdefault(leaf, {})
    if existing.get(SERVER_NAME) == entry:
        print(f"  {c.id}: already installed")
        return
    if SERVER_NAME in existing:
        print(f"  {c.id}: updating existing '{SERVER_NAME}' entry")

    if os.path.isfile(path):
        backup = _backup_path(path)
        shutil.copy2(path, backup)
        print(f"  backup: {backup}")

    existing[SERVER_NAME] = entry
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    print(f"  wrote {path}")


def install_opencode(t: Target, dirs, cmd, cmd_args, dry_run: bool) -> None:
    """Merge the server entry into opencode's JSONC global config.

    opencode's `mcp add` is interactive-only; its config schema for local
    servers is `mcp.<name> = {type: local, command: [...], environment: {...}}`.
    The file is JSONC (comments allowed) — parse with comment stripping, but
    write back plain JSON only when the original has no comments (else take a
    backup and merge textually is out of scope: refuse and point at the docs).
    """
    path = resolve_config_path(t.client)
    if path is None:
        print(f"Error: could not resolve config path for {t.client.name}.", file=sys.stderr)
        sys.exit(1)
    entry = {
        "type": "local",
        "command": [cmd, *cmd_args],
        "environment": {"SKILL_CATALOG_DIRS": ":".join(dirs)},
        "enabled": True,
    }
    if dry_run:
        print(f"[dry-run] {t.client.id}: would merge into {path}")
        print("  " + json.dumps({SERVER_NAME: entry}))
        return
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    data: dict = {}
    raw = ""
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
        try:
            data = json.loads(_strip_jsonc(raw))
        except json.JSONDecodeError as e:
            print(f"Error: {path} is not valid JSON/JSONC ({e}); refusing to overwrite. "
                  f"Fix or remove the file, then retry.", file=sys.stderr)
            sys.exit(1)
    mcp = data.setdefault("mcp", {})
    if mcp.get(SERVER_NAME) == entry:
        print(f"  {t.client.id}: already installed")
        return
    if SERVER_NAME in mcp:
        print(f"  {t.client.id}: updating existing '{SERVER_NAME}' entry")
    mcp[SERVER_NAME] = entry
    if os.path.isfile(path):
        if _has_jsonc_comments(raw):
            print(f"Error: {path} contains comments; refusing to rewrite. "
                  f"Add the entry manually (see INSTALL.md #opencode), then retry.",
                  file=sys.stderr)
            sys.exit(1)
        backup = _backup_path(path)
        shutil.copy2(path, backup)
        print(f"  backup: {backup}")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    print(f"  wrote {path}")

def _strip_jsonc(text: str) -> str:
    text = re.sub(r"(?m)^[ \t]*//.*$", "", text)
    return re.sub(r"/\*[\s\S]*?\*/", "", text)

def _has_jsonc_comments(text: str) -> bool:
    stripped = _strip_jsonc(text)
    return len(stripped) != len(text)

def _backup_path(path: str) -> str:
    n = 1
    while os.path.exists(f"{path}.bak-{n}"):
        n += 1
    return f"{path}.bak-{n}"

# ── CLI hint (for agents without MCP) ───────────────────────────────────────

HINT_MARKER = "<!-- skill-search-cli -->"

HINT_BODY = """## skill-search (CLI)

Search the local skills catalog before writing code or executing tasks:

  skill-search search "<keywords>"      # find skills (name + description)
  skill-search search "plan|prd|guide"  # OR: match any keyword
  skill-search view <name>              # read the full skill
  skill-search list                  # list all cataloged skills

Catalog: `~/.agents/skills-catalog` (`SKILL_CATALOG_DIRS` to override).
"""

HINT_CANDIDATES = (
    "~/.claude/CLAUDE.md",
    "~/CLAUDE.md",
    "~/AGENTS.md",
    # "./CLAUDE.md", # Duplicated in user level. not required in project too.
    # "./AGENTS.md",
)

def hint_targets() -> list[str]:
    """Existing hint files, deduped by real path. Never creates files."""
    out, seen = [], set()
    for raw in HINT_CANDIDATES:
        p = os.path.expanduser(raw) if raw.startswith("~") else os.path.abspath(raw)
        if os.path.isfile(p):
            real = os.path.realpath(p)
            if real not in seen:
                seen.add(real)
                out.append(real)
    return out

def append_cli_hint(dry_run: bool) -> None:
    block = HINT_MARKER + "\n" + HINT_BODY
    targets = hint_targets()
    if not targets:
        print("  cli-hint: no CLAUDE.md/AGENTS.md found; nothing to do")
        return
    for path in targets:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if HINT_MARKER in content:
            print(f"  cli-hint: already present in {path}; skipping")
            continue
        if dry_run:
            print(f"[dry-run] cli-hint: would append to {path}")
            continue
        backup = _backup_path(path)
        shutil.copy2(path, backup)
        sep = "" if (not content or content.endswith("\n")) else "\n"
        # Append-only: existing content is never rewritten, only added to.
        with open(path, "a", encoding="utf-8") as f:
            f.write(sep + block)
        print(f"  cli-hint: appended to {path} (backup: {backup})")

def remove_cli_hint() -> None:
    """Remove our own hint block; leaves edited blocks untouched."""
    block = HINT_MARKER + "\n" + HINT_BODY
    for path in hint_targets():
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        start = content.find(HINT_MARKER)
        if start < 0:
            continue
        if content[start:start + len(block)] != block:
            print(f"  cli-hint: {path} has an edited block; leaving it untouched")
            continue
        backup = _backup_path(path)
        shutil.copy2(path, backup)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content[:start] + content[start + len(block):])
        print(f"  cli-hint: removed from {path} (backup: {backup})" )


# ── Uninstall ───────────────────────────────────────────────────────────────

def cmd_uninstall(args) -> None:
    if getattr(args, "cli_hint", False):
        remove_cli_hint()
    targets = select_targets(args.client or [], args.all)
    if not targets:
        print("Nothing to uninstall.")
        return

    failed = False
    for t in targets:
        c = t.client
        try:
            if c.id == "chatgpt":
                print(f"  {c.id}: remove the connector in ChatGPT settings "
                      f"(Apps & Connectors); nothing to do locally.")
            elif c.binary:
                if not shutil.which(c.binary):
                    print(f"  {c.id}: '{c.binary}' not found; nothing to do")
                    continue
                print(f"{c.id}: $ {c.binary} {' '.join(c.remove_args)}")
                result = subprocess.run([c.binary, *c.remove_args])
                if result.returncode != 0:
                    print(f"Error: {' '.join([c.binary, *c.remove_args[:2]])} "
                          f"exited with code {result.returncode}.", file=sys.stderr)
                    sys.exit(1)
            else:
                _uninstall_file_backed(c)
            print(f"  ok: {c.id}")
        except SystemExit:
            failed = True
    if failed:
        sys.exit(1)


def _uninstall_file_backed(c: Client) -> None:
    if c.id == "opencode":
        _uninstall_opencode(c)
        return
    path = resolve_config_path(c)
    if path is None or not os.path.isfile(path):
        print(f"  {c.id}: no config at {path}; nothing to do")
        return
    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error: {path} is not valid JSON ({e}); leaving it untouched.",
                  file=sys.stderr)
            sys.exit(1)

    node = data
    for key in c.json_key[:-1]:
        node = node.get(key, {})
        if not isinstance(node, dict):
            print(f"  {c.id}: no '{SERVER_NAME}' entry")
            return
    servers = node.get(c.json_key[-1], {})
    if SERVER_NAME not in servers:
        print(f"  {c.id}: no '{SERVER_NAME}' entry")
        return

    backup = _backup_path(path)
    shutil.copy2(path, backup)
    del servers[SERVER_NAME]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    print(f"  removed '{SERVER_NAME}' from {path} (backup: {backup})")

def _uninstall_opencode(c: Client) -> None:
    path = resolve_config_path(c)
    if path is None or not os.path.isfile(path):
        print(f"  {c.id}: no config at {path}; nothing to do")
        return
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    try:
        data = json.loads(_strip_jsonc(raw))
    except json.JSONDecodeError as e:
        print(f"Error: {path} is not valid JSON/JSONC ({e}); leaving it untouched.",
              file=sys.stderr)
        sys.exit(1)
    mcp = data.get("mcp", {})
    if SERVER_NAME not in mcp:
        print(f"  {c.id}: no '{SERVER_NAME}' entry")
        return
    if _has_jsonc_comments(raw):
        print(f"Error: {path} contains comments; refusing to rewrite. "
              f"Remove the '{SERVER_NAME}' key under `mcp` manually.", file=sys.stderr)
        sys.exit(1)
    backup = _backup_path(path)
    shutil.copy2(path, backup)
    del mcp[SERVER_NAME]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    print(f"  removed '{SERVER_NAME}' from {path} (backup: {backup})")


# ── Misc ────────────────────────────────────────────────────────────────────

def list_clients() -> None:
    print("Installable clients:\n")
    for c in CLIENTS:
        kind = "command-backed" if c.binary else ("remote" if c.id == "chatgpt" else "file-backed")
        print(f"  {c.id:<16} {c.name:<16} {kind}")
        if c.note:
            print(f"  {'':<16} note: {c.note}")
    print(f"\nUsage: skill-search install <id> [--dry-run] [--catalog DIR ...] [--cli-hint] | --all")


def print_chatgpt_instructions(dirs, dry_run: bool) -> None:
    cmd, cmd_args = resolve_server_command()
    run_cmd = " ".join([cmd, *cmd_args, "--http", "--host", "127.0.0.1", "--port", "8787"])
    print(f"""
ChatGPT cannot run local stdio MCP servers — it connects to remote HTTPS
endpoints via Developer Mode. Self-host the server:

  1. Run the server:
       {run_cmd}
     ('{cmd} -h' shows options; non-loopback hosts disable DNS-rebinding
     protection because a reverse proxy owns Host/Origin checks, TLS, auth.)
  2. Expose it over HTTPS (Caddy, nginx, cloudflared tunnel, ...).
  3. In ChatGPT: Settings → Apps & Connectors → enable Developer mode →
     Create → Name: skill-search, Server URL: https://your-domain/mcp
     Authentication: no auth.

WARNING: anyone who can reach the endpoint can read the whole catalog
(read-only). Keep it behind auth or a private network.
""")
    if dry_run:
        return
    print("Set SKILL_CATALOG_DIRS to your catalog dirs, colon-separated:")
    print(f"  SKILL_CATALOG_DIRS={':'.join(dirs)}")
