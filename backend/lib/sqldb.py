"""SQLite storage for CodeAtlas (swap to PostgreSQL by replacing connect() + placeholders)."""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

DB_PATH = os.environ.get("SQLITE_PATH", str(Path(__file__).parent.parent / "data" / "codeatlas.db"))
DATA_DIR = Path(os.environ.get("DATA_DIR", str(Path(__file__).parent.parent / "data")))
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
  password_hash TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS repos (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL, source TEXT NOT NULL,
  source_url TEXT, status TEXT NOT NULL, stage TEXT, progress REAL DEFAULT 0,
  files_total INTEGER DEFAULT 0, files_indexed INTEGER DEFAULT 0, files_skipped INTEGER DEFAULT 0,
  skipped TEXT DEFAULT '[]', languages TEXT DEFAULT '{}', symbol_count INTEGER DEFAULT 0,
  chunk_count INTEGER DEFAULT 0, error TEXT, has_git INTEGER DEFAULT 0, git_path TEXT,
  is_sample INTEGER DEFAULT 0, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS repos_user ON repos(user_id, created_at);
CREATE TABLE IF NOT EXISTS files (
  id TEXT PRIMARY KEY, repo_id TEXT NOT NULL, path TEXT NOT NULL, language TEXT,
  size INTEGER, line_count INTEGER, content TEXT, imports TEXT DEFAULT '[]',
  parsed INTEGER DEFAULT 0, description TEXT
);
CREATE INDEX IF NOT EXISTS files_repo ON files(repo_id, path);
CREATE TABLE IF NOT EXISTS symbols (
  id TEXT PRIMARY KEY, repo_id TEXT NOT NULL, file_path TEXT NOT NULL, name TEXT NOT NULL,
  kind TEXT NOT NULL, language TEXT, start_line INTEGER, end_line INTEGER, params TEXT,
  returns TEXT, parent TEXT, docstring TEXT, signature TEXT, calls TEXT DEFAULT '[]', is_test INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS symbols_repo ON symbols(repo_id, file_path);
CREATE INDEX IF NOT EXISTS symbols_name ON symbols(repo_id, name);
CREATE TABLE IF NOT EXISTS edges (
  repo_id TEXT NOT NULL, source_id TEXT NOT NULL, target_id TEXT NOT NULL, kind TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS edges_src ON edges(repo_id, source_id);
CREATE INDEX IF NOT EXISTS edges_tgt ON edges(repo_id, target_id);
CREATE TABLE IF NOT EXISTS chunks (
  id TEXT PRIMARY KEY, repo_id TEXT NOT NULL, file_path TEXT NOT NULL, symbol_id TEXT,
  symbol_name TEXT, symbol_kind TEXT, start_line INTEGER, end_line INTEGER, language TEXT, content TEXT
);
CREATE INDEX IF NOT EXISTS chunks_repo ON chunks(repo_id);
CREATE TABLE IF NOT EXISTS conversations (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, repo_id TEXT, title TEXT, created_at TEXT, updated_at TEXT
);
CREATE INDEX IF NOT EXISTS conv_user ON conversations(user_id, updated_at);
CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL,
  mode TEXT, scope TEXT, evidence TEXT DEFAULT '[]', confidence TEXT, selection TEXT, created_at TEXT
);
CREATE INDEX IF NOT EXISTS msg_conv ON messages(conversation_id, created_at);
CREATE TABLE IF NOT EXISTS quizzes (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, repo_id TEXT, repo_name TEXT, kind TEXT, topic TEXT,
  difficulty TEXT, questions TEXT, answers TEXT DEFAULT '{}', status TEXT, score INTEGER DEFAULT 0,
  total INTEGER DEFAULT 0, results TEXT, created_at TEXT, completed_at TEXT
);
CREATE INDEX IF NOT EXISTS quiz_user ON quizzes(user_id, created_at);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as c:
        c.executescript(SCHEMA)


def query(sql: str, params: Iterable[Any] = ()) -> list[dict]:
    with connect() as c:
        return [dict(r) for r in c.execute(sql, tuple(params)).fetchall()]


def query_one(sql: str, params: Iterable[Any] = ()) -> dict | None:
    with connect() as c:
        r = c.execute(sql, tuple(params)).fetchone()
        return dict(r) if r else None


def execute(sql: str, params: Iterable[Any] = ()) -> None:
    with connect() as c:
        c.execute(sql, tuple(params))


def executemany(sql: str, rows: list[tuple]) -> None:
    with connect() as c:
        c.executemany(sql, rows)


def jload(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return default
