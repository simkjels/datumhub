"""SQLite database setup and connection management."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

import datumhub.config as _config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS api_tokens (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token       TEXT UNIQUE NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at  TEXT NOT NULL DEFAULT (datetime('now', '+90 days'))
);

CREATE TABLE IF NOT EXISTS packages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    package_id      TEXT NOT NULL,
    version         TEXT NOT NULL,
    owner_id        INTEGER NOT NULL REFERENCES users(id),
    data            TEXT NOT NULL,
    published_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(package_id, version)
);

CREATE INDEX IF NOT EXISTS idx_packages_id ON packages(package_id);
"""

_conn: Optional[sqlite3.Connection] = None


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """Apply incremental schema migrations. Idempotent."""
    # A1: add expires_at to api_tokens if not present
    cols = {row[1] for row in conn.execute("PRAGMA table_info(api_tokens)")}
    if "expires_at" not in cols:
        conn.execute(
            "ALTER TABLE api_tokens ADD COLUMN expires_at TEXT "
            "NOT NULL DEFAULT (datetime('now', '+90 days'))"
        )
        conn.commit()


def _setup_fts(conn: sqlite3.Connection) -> None:
    """Create FTS5 virtual table and sync triggers. Idempotent."""
    try:
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS packages_fts USING fts5(
                package_id,
                title,
                description,
                tags,
                publisher_name
            )
        """)
        # Insert trigger
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS packages_fts_ai
            AFTER INSERT ON packages BEGIN
                INSERT INTO packages_fts(
                    rowid, package_id, title, description, tags, publisher_name
                ) VALUES (
                    new.id,
                    new.package_id,
                    json_extract(new.data, '$.title'),
                    COALESCE(json_extract(new.data, '$.description'), ''),
                    COALESCE(json_extract(new.data, '$.tags'), ''),
                    json_extract(new.data, '$.publisher.name')
                );
            END
        """)
        # Delete trigger
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS packages_fts_ad
            AFTER DELETE ON packages BEGIN
                DELETE FROM packages_fts WHERE rowid = old.id;
            END
        """)
        # Update trigger (delete old FTS entry, insert new)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS packages_fts_au
            AFTER UPDATE ON packages BEGIN
                DELETE FROM packages_fts WHERE rowid = old.id;
                INSERT INTO packages_fts(
                    rowid, package_id, title, description, tags, publisher_name
                ) VALUES (
                    new.id,
                    new.package_id,
                    json_extract(new.data, '$.title'),
                    COALESCE(json_extract(new.data, '$.description'), ''),
                    COALESCE(json_extract(new.data, '$.tags'), ''),
                    json_extract(new.data, '$.publisher.name')
                );
            END
        """)
        conn.commit()
    except sqlite3.OperationalError:
        # FTS5 not available in this SQLite build — search falls back to LIKE
        pass


def _backfill_fts(conn: sqlite3.Connection) -> None:
    """Insert any packages not yet present in the FTS index."""
    try:
        conn.execute("""
            INSERT INTO packages_fts(
                rowid, package_id, title, description, tags, publisher_name
            )
            SELECT
                p.id,
                p.package_id,
                json_extract(p.data, '$.title'),
                COALESCE(json_extract(p.data, '$.description'), ''),
                COALESCE(json_extract(p.data, '$.tags'), ''),
                json_extract(p.data, '$.publisher.name')
            FROM packages p
            WHERE p.id NOT IN (SELECT rowid FROM packages_fts)
        """)
        conn.commit()
    except sqlite3.OperationalError:
        pass


def init_db(path: Optional[Path] = None) -> None:
    """Initialise the database. Call once at startup."""
    global _conn
    db_path = path or _config.DB_PATH
    if _conn is not None:
        _conn.close()
    _conn = sqlite3.connect(str(db_path), check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _conn.executescript(SCHEMA)
    _conn.commit()
    _migrate_schema(_conn)
    _setup_fts(_conn)
    _backfill_fts(_conn)


def get_db() -> sqlite3.Connection:
    if _conn is None:
        raise RuntimeError("Database not initialised — call init_db() first.")
    return _conn
