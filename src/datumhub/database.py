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
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
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


def get_db() -> sqlite3.Connection:
    if _conn is None:
        raise RuntimeError("Database not initialised — call init_db() first.")
    return _conn
