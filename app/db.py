import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

from app.storage import db_path, ensure_dirs

SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    title TEXT,
    thumb_path TEXT,
    thumb_mode TEXT NOT NULL DEFAULT 'gif',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
);

CREATE TABLE IF NOT EXISTS entry_tags (
    entry_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (entry_id, tag_id)
);
"""


@dataclass
class Entry:
    id: int
    url: str
    title: str
    thumb_path: str  # file name only; resolve with storage.thumb_file()
    thumb_mode: str
    created_at: str
    tags: list[str] = field(default_factory=list)


@contextmanager
def connect():
    ensure_dirs()
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        _prune_unused_tags(conn)


def _prune_unused_tags(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM tags WHERE id NOT IN (SELECT tag_id FROM entry_tags)")


def _clean(text: str) -> str:
    # Control chars have no place in tags/search: NUL truncates SQLite LIKE
    # patterns (turning "\x00x" into match-all) and \x1f is our tag separator.
    return "".join(ch for ch in text if ch.isprintable()).strip()


def _get_or_create_tag_ids(conn: sqlite3.Connection, tag_names: Iterable[str]) -> list[int]:
    ids = []
    for raw in tag_names:
        name = _clean(raw)
        if not name:
            continue
        conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,))
        row = conn.execute("SELECT id FROM tags WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
        ids.append(row["id"])
    return ids


def add_entry(url: str, title: str, thumb_path: str, thumb_mode: str, tag_names: Iterable[str]) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO entries (url, title, thumb_path, thumb_mode, created_at) VALUES (?, ?, ?, ?, ?)",
            (url, title, thumb_path, thumb_mode, datetime.now(timezone.utc).isoformat()),
        )
        entry_id = cur.lastrowid
        for tag_id in _get_or_create_tag_ids(conn, tag_names):
            conn.execute(
                "INSERT OR IGNORE INTO entry_tags (entry_id, tag_id) VALUES (?, ?)",
                (entry_id, tag_id),
            )
        return entry_id


def update_entry(entry_id: int, url: str, title: str, thumb_path: str, thumb_mode: str, tag_names: Iterable[str]) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE entries SET url = ?, title = ?, thumb_path = ?, thumb_mode = ? WHERE id = ?",
            (url, title, thumb_path, thumb_mode, entry_id),
        )
        conn.execute("DELETE FROM entry_tags WHERE entry_id = ?", (entry_id,))
        for tag_id in _get_or_create_tag_ids(conn, tag_names):
            conn.execute(
                "INSERT OR IGNORE INTO entry_tags (entry_id, tag_id) VALUES (?, ?)",
                (entry_id, tag_id),
            )
        _prune_unused_tags(conn)


def delete_entry(entry_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
        _prune_unused_tags(conn)


def get_all_tags() -> list[str]:
    """Most-used tags first, ties alphabetical."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT t.name FROM tags t
            LEFT JOIN entry_tags et ON et.tag_id = t.id
            GROUP BY t.id
            ORDER BY COUNT(et.entry_id) DESC, t.name COLLATE NOCASE
            """
        ).fetchall()
        return [r["name"] for r in rows]


# Tags are fetched alongside each entry (instead of one query per entry),
# joined with the ASCII unit separator, which can't appear in a typed tag.
TAG_SEP = "\x1f"
ENTRY_SELECT = """
    SELECT e.*, (
        SELECT GROUP_CONCAT(t.name, char(31))
        FROM entry_tags x JOIN tags t ON t.id = x.tag_id
        WHERE x.entry_id = e.id
    ) AS tag_list
    FROM entries e
"""


def _row_to_entry(row: sqlite3.Row) -> Entry:
    tags = row["tag_list"].split(TAG_SEP) if row["tag_list"] else []
    return Entry(
        id=row["id"],
        url=row["url"],
        title=row["title"] or "",
        thumb_path=row["thumb_path"] or "",
        thumb_mode=row["thumb_mode"],
        created_at=row["created_at"],
        tags=sorted(tags, key=str.lower),
    )


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_entries(tag_names: Iterable[str], text: str = "") -> list[Entry]:
    # Dedupe case-insensitively, or "Cats" + "cats" could never satisfy the HAVING count.
    tag_names = list({_clean(t).lower(): _clean(t) for t in tag_names if _clean(t)}.values())
    text = _clean(text)

    with connect() as conn:
        query = ENTRY_SELECT
        params: list = []

        if tag_names:
            # tags.name is COLLATE NOCASE, so IN matches case-insensitively.
            placeholders = ",".join("?" for _ in tag_names)
            query += f"""
                JOIN entry_tags et ON et.entry_id = e.id
                JOIN tags t ON t.id = et.tag_id AND t.name IN ({placeholders})
            """
            params.extend(tag_names)

        if text:
            pattern = f"%{_escape_like(text)}%"
            query += """
                WHERE (
                    e.title LIKE ? ESCAPE '\\' OR e.url LIKE ? ESCAPE '\\'
                    OR EXISTS (
                        SELECT 1 FROM entry_tags st JOIN tags s ON s.id = st.tag_id
                        WHERE st.entry_id = e.id AND s.name LIKE ? ESCAPE '\\'
                    )
                )
            """
            params.extend([pattern] * 3)

        if tag_names:
            query += " GROUP BY e.id HAVING COUNT(DISTINCT t.id) = ?"
            params.append(len(tag_names))

        query += " ORDER BY e.created_at DESC"

        return [_row_to_entry(row) for row in conn.execute(query, params)]


def get_entry(entry_id: int) -> Entry | None:
    with connect() as conn:
        row = conn.execute(ENTRY_SELECT + " WHERE e.id = ?", (entry_id,)).fetchone()
        return _row_to_entry(row) if row else None
