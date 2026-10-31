"""SQLite data layer used by the auth flows."""
import sqlite3

DB_PATH = "demo.db"


def get_connection():
    """Open a connection with dict-like rows."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def database_query(sql, params=(), fetch_one=False):
    """Run a SQL statement and return rows (or a single row)."""
    conn = get_connection()
    try:
        cur = conn.execute(sql, params)
        conn.commit()
        if fetch_one:
            return cur.fetchone()
        return cur.fetchall()
    finally:
        conn.close()


def init_schema():
    """Create tables if they do not exist."""
    database_query("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, email TEXT UNIQUE, password_hash TEXT, name TEXT)")
    database_query("CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER)")


def get_user(email):
    """Look up a user by email."""
    row = database_query("SELECT * FROM users WHERE email = ?", (email,), fetch_one=True)
    return dict(row) if row else None


def insert_user(email, password_hash, name):
    """Insert a user and return its id."""
    database_query("INSERT INTO users (email, password_hash, name) VALUES (?, ?, ?)", (email, password_hash, name))
    return get_user(email)["id"]


def save_session(user_id, token):
    """Persist a session token."""
    database_query("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
