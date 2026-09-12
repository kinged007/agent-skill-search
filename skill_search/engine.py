"""
Core search engine for SKILL.md catalogs.

Scans directories for SKILL.md files, parses YAML frontmatter,
and builds an FTS5-backed search index for fast relevance queries.
"""

import os
import re
import shlex
import sqlite3
import hashlib
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

# ── Known agent skills locations ────────────────────────────────────────────
# Home-relative skills dirs owned by other agent tools. Only existing ones are
# ever used, so listing a client you don't have installed costs nothing.
KNOWN_SKILL_DIRS = (
    "~/.agents/skills",
    "~/.config/opencode/skills",
    "~/.claude/skills",
    "~/.codex/skills",
    "~/.cursor/skills",
    "~/.gemini/skills",
    "~/.hermes/skills",
    "~/.opencode/skills",
    "~/skills",
    "./.agents/skills",
)

INCLUDE_KNOWN_ENV = "SKILL_INCLUDE_KNOWN"

def include_known_dirs() -> bool:
    """True when SKILL_INCLUDE_KNOWN=1 (also accepts true/yes/on)."""
    return os.environ.get(INCLUDE_KNOWN_ENV, "").strip().lower() in ("1", "true", "yes", "on")

def existing_known_dirs() -> list[str]:
    """Known skills dirs that exist, deduped by real path (symlinks collapse)."""
    out, seen = [], set()
    for d in KNOWN_SKILL_DIRS:
        expanded = os.path.expanduser(d)
        if os.path.isdir(expanded):
            real = os.path.realpath(expanded)
            if real not in seen:
                seen.add(real)
                out.append(real)
    return out


@dataclass
class SkillEntry:
    name: str
    description: str
    category: str
    path: str  # absolute path to SKILL.md
    content: str  # full markdown body (after frontmatter)


def parse_skill_md(filepath: str) -> Optional[SkillEntry]:
    """Parse a SKILL.md file into a SkillEntry."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            raw = f.read()
    except (OSError, UnicodeDecodeError):
        return None

    # Parse YAML frontmatter
    if not raw.startswith("---"):
        return None

    end = raw.find("---", 3)
    if end == -1:
        return None

    frontmatter_raw = raw[3:end].strip()
    body = raw[end + 3:].strip()

    # Simple YAML parser (no dependency needed)
    meta = {}
    for line in frontmatter_raw.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            # Handle list values like [python, automation]
            if value.startswith("[") and value.endswith("]"):
                value = value[1:-1]
            meta[key] = value

    name = meta.get("name", "")
    description = meta.get("description", "")
    category = meta.get("category", meta.get("metadata", ""))

    # Try to extract category from nested metadata if present
    if not category:
        for line in frontmatter_raw.split("\n"):
            stripped = line.strip()
            if stripped.startswith("category:"):
                category = stripped.split(":", 1)[1].strip().strip('"').strip("'")
                break

    if not name:
        # Fall back to directory name
        name = Path(filepath).parent.name

    if not description:
        # First non-empty line of body as fallback
        for line in body.split("\n"):
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                description = stripped[:500]
                break

    return SkillEntry(
        name=name,
        description=description,
        category=category,
        path=os.path.abspath(filepath),
        content=body,
    )


def scan_catalog(*dirs: str) -> list[SkillEntry]:
    """Scan directories for SKILL.md files and return parsed entries.

    Deduplicates by skill name (first dir wins) so the same skill installed
    in several agent folders is indexed once. Identical files reached through
    symlinks are skipped via real-path tracking.
    """
    entries = []
    seen_names = set()
    seen_files = set()

    for d in dirs:
        d = os.path.expanduser(d)
        if not os.path.isdir(d):
            continue

        for root, _, files in os.walk(d):
            for f in files:
                if f.upper() == "SKILL.MD":
                    fp = os.path.realpath(os.path.join(root, f))
                    if fp in seen_files:
                        continue
                    seen_files.add(fp)
                    entry = parse_skill_md(fp)
                    if entry:
                        key = entry.name.strip().casefold()
                        if key not in seen_names:
                            entries.append(entry)
                            seen_names.add(key)

    return entries


class SkillIndex:
    """FTS5-backed search index for skills."""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._init_db()

    def _init_db(self):
        self.conn.execute("DROP TABLE IF EXISTS skills")
        self.conn.execute("""
            CREATE TABLE skills (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT,
                path TEXT NOT NULL,
                content TEXT NOT NULL
            )
        """)
        # FTS5 virtual table for full-text search
        self.conn.execute("DROP TABLE IF EXISTS skills_fts")
        self.conn.execute("""
            CREATE VIRTUAL TABLE skills_fts USING fts5(
                name, description, category, content,
                content='skills',
                content_rowid='id',
                tokenize='porter unicode61'
            )
        """)
        self.conn.commit()

    def build(self, entries: list[SkillEntry]):
        """Index a list of SkillEntry objects."""
        for e in entries:
            self.conn.execute(
                "INSERT INTO skills (name, description, category, path, content) VALUES (?, ?, ?, ?, ?)",
                (e.name, e.description, e.category, e.path, e.content),
            )
            self.conn.execute(
                "INSERT INTO skills_fts (rowid, name, description, category, content) VALUES (last_insert_rowid(), ?, ?, ?, ?)",
                (e.name, e.description, e.category, e.content),
            )
        self.conn.commit()

    @staticmethod
    def _normalize_query(query: str) -> str:
        """Translate user-friendly `a|b|c` into FTS5 `"a" OR "b" OR "c"`.

        Single queries pass through unchanged. Quoted phrases inside a
        segment are preserved; other tokens are quoted (disables FTS5
        operators inside user input — ponytail: expose raw FTS5 syntax
        via a --raw flag when users ask for NEAR/column filters).
        """
        if "|" not in query:
            return query
        parts = []
        for raw in query.split("|"):
            segment = raw.strip()
            if not segment:
                continue
            try:
                tokens = shlex.split(segment)
            except ValueError:
                tokens = [segment]
            quoted = " ".join(f'"{t}"' for t in tokens)
            if quoted:
                parts.append(quoted)
        return " OR ".join(parts) if parts else query

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search skills by query. Returns ranked results with snippets.

        Query syntax: space-separated tokens (implicit AND), pipe-separated
        tokens (`a|b|c` → `a OR b OR c`), and double-quoted phrases.
        """
        query = self._normalize_query(query)
        if not query.strip():
            return self.list_all(limit)

        # Try FTS5 search first
        try:
            rows = self.conn.execute("""
                SELECT s.name, s.description, s.category, s.path,
                       rank
                FROM skills_fts f
                JOIN skills s ON s.id = f.rowid
                WHERE skills_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, limit)).fetchall()
        except sqlite3.OperationalError:
            # FTS5 query syntax error — fall back to LIKE
            like_q = f"%{query}%"
            rows = self.conn.execute("""
                SELECT name, description, category, path, 0.0
                FROM skills
                WHERE name LIKE ? OR description LIKE ? OR category LIKE ? OR content LIKE ?
                ORDER BY
                    CASE WHEN name LIKE ? THEN 0 ELSE 1 END,
                    CASE WHEN description LIKE ? THEN 0 ELSE 1 END
                LIMIT ?
            """, (like_q, like_q, like_q, like_q, like_q, like_q, limit)).fetchall()

        return [
            {
                "name": r[0],
                "description": r[1],
                "category": r[2] or "",
                "path": r[3],
                "relevance": round(-r[4], 3) if r[4] else 1.0,
            }
            for r in rows
        ]

    def list_all(self, limit: int = 100) -> list[dict]:
        """List all indexed skills."""
        rows = self.conn.execute(
            "SELECT name, description, category, path FROM skills ORDER BY name LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {"name": r[0], "description": r[1], "category": r[2] or "", "path": r[3]}
            for r in rows
        ]

    def get_skill(self, name: str) -> Optional[dict]:
        """Get a skill by exact name."""
        row = self.conn.execute(
            "SELECT name, description, category, path, content FROM skills WHERE name = ?",
            (name,),
        ).fetchone()
        if row:
            return {
                "name": row[0],
                "description": row[1],
                "category": row[2] or "",
                "path": row[3],
                "content": row[4],
            }
        return None

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0]

    def close(self):
        self.conn.close()


def build_index(*catalog_dirs: str, db_path: str = ":memory:") -> SkillIndex:
    """Scan catalogs and build a search index. Returns ready-to-query SkillIndex."""
    entries = scan_catalog(*catalog_dirs)
    index = SkillIndex(db_path)
    index.build(entries)
    return index
