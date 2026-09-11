"""
CLI for Skill Search.

Usage:
    skill-search search <query> [--limit N]
    skill-search view <name>
    skill-search list [--limit N]
    skill-search add <skills-dir>    # Move skills into catalog

Catalog dirs: --dirs flag > SKILL_CATALOG_DIRS env > defaults
(~/.agents/skills-catalog, ./.agents/skills-catalog).
--include-known (or SKILL_INCLUDE_KNOWN=1) additionally scans well-known
agent skills locations (opencode, claude, codex, ...). Same-named skills
are deduplicated, first dir wins.
"""

import os
import sys
import json
import shutil
import argparse
from pathlib import Path

from .engine import (
    build_index,
    SkillIndex,
    existing_known_dirs,
    include_known_dirs,
)

# ── Catalog resolution ──────────────────────────────────────────────────────

DEFAULT_CATALOG = "~/.agents/skills-catalog"
LOCAL_CATALOG = "./.agents/skills-catalog"

def _flag(args, name, default):
    """Common flag readable wherever it was given (global or subcommand)."""
    return getattr(args, name, default)

def want_known(args) -> bool:
    """--include-known/--no-include-known flag, falling back to the env var."""
    flag = _flag(args, "include_known", None)
    if flag is not None:
        return flag
    return include_known_dirs()

def get_catalog_dirs(extra: str = None, include_known: bool = False) -> list[str]:
    """Resolve catalog directories. Explicit dirs first, then known, then defaults."""
    dirs = []

    # Explicit dirs from CLI flag
    if extra:
        dirs.extend(d.strip() for d in extra.split(":") if d.strip())

    # Explicit dirs from env
    env = os.environ.get("SKILL_CATALOG_DIRS", "")
    if env:
        dirs.extend(d.strip() for d in env.split(":") if d.strip())

    # Well-known agent skills locations (opencode, claude, codex, ...)
    if include_known:
        dirs.extend(existing_known_dirs())

    # If no explicit dirs, use defaults
    if not dirs:
        for d in [DEFAULT_CATALOG, LOCAL_CATALOG]:
            expanded = os.path.expanduser(d)
            if os.path.isdir(expanded):
                dirs.append(expanded)

    # Deduplicate, preserve order, verify existence
    seen = set()
    result = []
    for d in dirs:
        expanded = os.path.expanduser(d)
        if not os.path.isdir(expanded):
            continue
        real = os.path.realpath(expanded)
        if real not in seen:
            seen.add(real)
            result.append(real)
    return result

def ensure_catalog_exists() -> str:
    """Create the default catalog dir if it doesn't exist. Returns the path."""
    cat = os.path.expanduser(DEFAULT_CATALOG)
    os.makedirs(cat, exist_ok=True)
    return cat

# ── Commands ────────────────────────────────────────────────────────────────

def cmd_search(args):
    dirs = get_catalog_dirs(_flag(args, "dirs", None), want_known(args))
    if not dirs:
        print("Error: No catalog directories found.", file=sys.stderr)
        print(f"Create one: mkdir -p {DEFAULT_CATALOG}", file=sys.stderr)
        print("Or set SKILL_CATALOG_DIRS=dir1:dir2", file=sys.stderr)
        sys.exit(1)

    index = build_index(*dirs)
    results = index.search(args.query, limit=args.limit)

    if not results:
        print(f"No skills found for '{args.query}'")
        return

    if _flag(args, "json", False):
        print(json.dumps(results, indent=2))
    else:
        print(f"Found {len(results)} skill(s) for '{args.query}':\n")
        for i, r in enumerate(results, 1):
            print(f"  {i}. {r['name']}")
            print(f"     {r['description'][:150]}")
            print()

def cmd_view(args):
    dirs = get_catalog_dirs(_flag(args, "dirs", None), want_known(args))
    if not dirs:
        print("Error: No catalog directories found.", file=sys.stderr)
        sys.exit(1)

    index = build_index(*dirs)
    result = index.get_skill(args.name)

    if not result:
        # Fuzzy fallback
        results = index.search(args.name, limit=1)
        if results:
            print(f"Skill '{args.name}' not found. Did you mean '{results[0]['name']}'?",
                  file=sys.stderr)
        else:
            print(f"Skill '{args.name}' not found in catalog.", file=sys.stderr)
        sys.exit(1)

    print(result["content"])

def cmd_list(args):
    dirs = get_catalog_dirs(_flag(args, "dirs", None), want_known(args))
    if not dirs:
        print("Error: No catalog directories found.", file=sys.stderr)
        sys.exit(1)

    index = build_index(*dirs)
    results = index.list_all(limit=args.limit)

    if _flag(args, "json", False):
        print(json.dumps(results, indent=2))
    else:
        print(f"Catalog: {index.count()} skill(s)\n")
        current_cat = None
        for r in results:
            cat = r.get("category", "")
            if cat != current_cat:
                current_cat = cat
                print(f"\n  [{cat or 'uncategorized'}]")
            print(f"    {r['name']}: {r['description'][:100]}")
        print()

def cmd_add(args):
    """Move skills from a source directory into the catalog."""
    src = os.path.expanduser(args.source)
    if not os.path.isdir(src):
        print(f"Error: '{src}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    catalog = os.path.expanduser(DEFAULT_CATALOG)
    os.makedirs(catalog, exist_ok=True)

    # Scan source for SKILL.md files to find skill directories
    moved = 0
    skipped = 0

    for item in sorted(os.listdir(src)):
        item_path = os.path.join(src, item)
        if not os.path.isdir(item_path):
            continue

        # Check if this directory contains a SKILL.md
        skill_md = os.path.join(item_path, "SKILL.md")
        if not os.path.isfile(skill_md):
            # Check one level deeper (e.g., src/category/skill-name/SKILL.md)
            for sub in os.listdir(item_path):
                sub_path = os.path.join(item_path, sub)
                if os.path.isdir(sub_path) and os.path.isfile(os.path.join(sub_path, "SKILL.md")):
                    skill_md = os.path.join(sub_path, "SKILL.md")
                    item_path = sub_path
                    item = sub
                    break
            else:
                skipped += 1
                continue

        dest = os.path.join(catalog, item)
        if os.path.exists(dest):
            print(f"  Skip (exists): {item}")
            skipped += 1
            continue

        shutil.move(item_path, dest)
        print(f"  Moved: {item} → {catalog}/")
        moved += 1

    print(f"\nDone: {moved} moved, {skipped} skipped")
    print(f"Catalog: {catalog}")

# ── Main ────────────────────────────────────────────────────────────────────

def _add_common_flags(p, is_sub=False):
    """Flags accepted both globally and after the subcommand.

    Subcommand copies use SUPPRESS defaults so they never clobber a value
    already given globally — either position works and they combine.
    """
    d = argparse.SUPPRESS if is_sub else None
    p.add_argument("--dirs", default=d, help="Additional catalog dirs (colon-separated)")
    p.add_argument("--json", action="store_true", default=(d if is_sub else False),
                   help="Output as JSON")
    p.add_argument("--include-known", dest="include_known", action="store_true",
                   default=d, help="Also scan well-known agent skills dirs")
    p.add_argument("--no-include-known", dest="include_known", action="store_false",
                   help="Do not scan well-known agent skills dirs")

def main():
    parser = argparse.ArgumentParser(
        prog="skill-search",
        description="Universal skill search — find relevant skills from your catalog",
    )
    _add_common_flags(parser)

    sub = parser.add_subparsers(dest="command")

    p_search = sub.add_parser("search", help="Search skills by keyword")
    p_search.add_argument("query", help="Search query (grep-style)")
    p_search.add_argument("--limit", type=int, default=10, help="Max results")
    _add_common_flags(p_search, is_sub=True)

    p_view = sub.add_parser("view", help="View full skill content")
    p_view.add_argument("name", help="Skill name")
    _add_common_flags(p_view, is_sub=True)

    p_list = sub.add_parser("list", help="List all skills")
    p_list.add_argument("--limit", type=int, default=100, help="Max results")
    _add_common_flags(p_list, is_sub=True)

    p_add = sub.add_parser("add", help="Move skills from a directory into the catalog")
    p_add.add_argument("source", help="Source skills directory to move from")

    p_install = sub.add_parser("install", help="Install the MCP server into an agent client")
    p_install.add_argument("client", nargs="*", help="Client id(s) — see --list")
    p_install.add_argument("--list", action="store_true", help="List known clients")
    p_install.add_argument("--all", action="store_true", help="Install into every detected client")
    p_install.add_argument("--dry-run", action="store_true", help="Print what would be done; write nothing")
    p_install.add_argument("--catalog", action="append", help="Catalog dir (repeatable)")
    p_install.add_argument("--cli-hint", action="store_true",
                           help="Append CLI usage snippet to existing CLAUDE.md/AGENTS.md (never overwrites)")
    p_install.add_argument("--include-known", dest="include_known", action="store_true",
                           default=None, help="Also scan well-known agent skills dirs")
    p_install.add_argument("--no-include-known", dest="include_known", action="store_false",
                           help="Do not scan well-known agent skills dirs")

    p_uninstall = sub.add_parser("uninstall", help="Remove the MCP server from an agent client")
    p_uninstall.add_argument("client", nargs="*", help="Client id(s) — see install --list")
    p_uninstall.add_argument("--all", action="store_true", help="Uninstall from every detected client")
    p_uninstall.add_argument("--cli-hint", action="store_true",
                             help="Also remove the CLI usage snippet from CLAUDE.md/AGENTS.md")

    args = parser.parse_args()

    if args.command == "search":
        cmd_search(args)
    elif args.command == "view":
        cmd_view(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "add":
        cmd_add(args)
    elif args.command == "install":
        from .install import cmd_install
        cmd_install(args)
    elif args.command == "uninstall":
        from .install import cmd_uninstall
        cmd_uninstall(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
