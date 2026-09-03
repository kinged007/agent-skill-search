"""
CLI for Skill Search.

Usage:
    skill-search search <query> [--limit N]
    skill-search view <name>
    skill-search list [--limit N]
    skill-search add <skills-dir>    # Move skills into catalog

Set SKILL_CATALOG_DIRS=dir1:dir2 to specify additional catalog directories.
Defaults: ~/.agents/skills-catalog, ./.agents/skills-catalog
"""

import os
import sys
import json
import shutil
import argparse
from pathlib import Path

from .engine import build_index, SkillIndex


# ── Catalog resolution ──────────────────────────────────────────────────────

DEFAULT_CATALOG = "~/.agents/skills-catalog"
LOCAL_CATALOG = "./.agents/skills-catalog"


def get_catalog_dirs(extra: str = None) -> list[str]:
    """Resolve catalog directories. Defaults + optional overrides."""
    dirs = []

    # Explicit dirs from CLI flag
    if extra:
        dirs.extend(d.strip() for d in extra.split(":") if d.strip())

    # Explicit dirs from env
    env = os.environ.get("SKILL_CATALOG_DIRS", "")
    if env:
        dirs.extend(d.strip() for d in env.split(":") if d.strip())

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
        real = os.path.realpath(os.path.expanduser(d))
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
    dirs = get_catalog_dirs(args.dirs)
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

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"Found {len(results)} skill(s) for '{args.query}':\n")
        for i, r in enumerate(results, 1):
            print(f"  {i}. {r['name']}")
            print(f"     {r['description'][:150]}")
            print()


def cmd_view(args):
    dirs = get_catalog_dirs(args.dirs)
    if not dirs:
        print("Error: No catalog directories found.", file=sys.stderr)
        sys.exit(1)

    index = build_index(*dirs)
    result = index.get_skill(args.name)

    if not result:
        # Fuzzy fallback
        results = index.search(args.name, limit=1)
        if results:
            print(f"Skill '{args.name}' not found. Did you mean '{results[0]['name']}'?")
        else:
            print(f"Skill '{args.name}' not found in catalog.")
        sys.exit(1)

    print(result["content"])


def cmd_list(args):
    dirs = get_catalog_dirs(args.dirs)
    if not dirs:
        print("Error: No catalog directories found.", file=sys.stderr)
        sys.exit(1)

    index = build_index(*dirs)
    results = index.list_all(limit=args.limit)

    if args.json:
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

def main():
    parser = argparse.ArgumentParser(
        prog="skill-search",
        description="Universal skill search — find relevant skills from your catalog",
    )
    parser.add_argument("--dirs", help="Additional catalog dirs (colon-separated)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    sub = parser.add_subparsers(dest="command")

    p_search = sub.add_parser("search", help="Search skills by keyword")
    p_search.add_argument("query", help="Search query (grep-style)")
    p_search.add_argument("--limit", type=int, default=10, help="Max results")

    p_view = sub.add_parser("view", help="View full skill content")
    p_view.add_argument("name", help="Skill name")

    p_list = sub.add_parser("list", help="List all skills")
    p_list.add_argument("--limit", type=int, default=100, help="Max results")

    p_add = sub.add_parser("add", help="Move skills from a directory into the catalog")
    p_add.add_argument("source", help="Source skills directory to move from")

    p_install = sub.add_parser("install", help="Install the MCP server into an agent client")
    p_install.add_argument("client", nargs="*", help="Client id(s) — see --list")
    p_install.add_argument("--list", action="store_true", help="List known clients")
    p_install.add_argument("--all", action="store_true", help="Install into every detected client")
    p_install.add_argument("--dry-run", action="store_true", help="Print what would be done; write nothing")
    p_install.add_argument("--catalog", action="append", help="Catalog dir (repeatable)")

    p_uninstall = sub.add_parser("uninstall", help="Remove the MCP server from an agent client")
    p_uninstall.add_argument("client", nargs="*", help="Client id(s) — see install --list")
    p_uninstall.add_argument("--all", action="store_true", help="Uninstall from every detected client")

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
