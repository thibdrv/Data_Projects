"""Database access: strictly read-only, PII-free.

- The connection is opened with SQLite's read-only mode, so any write fails at the engine level.
- No credentials are needed or stored (SQLite is a local file).
- Customer data comes from the `v_customers_analytics` view (no name, email or phone).
- Queries are parameterised; never build SQL with f-strings.
"""
import os
import sqlite3
from pathlib import Path

DB_PATH = os.getenv("DB_PATH", "data/customers.db")

CUSTOMER_VIEW = "v_customers_analytics"


def connect(path=None):
    """Open the database read-only. Raises sqlite3.OperationalError if the file is missing."""
    uri = Path(path or DB_PATH).resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def get_customers(conn):
    """All customers as dicts, without PII (name, email, phone)."""
    rows = conn.execute(f"SELECT * FROM {CUSTOMER_VIEW}").fetchall()  # constant, not user input
    return [dict(r) for r in rows]


def get_customers_by_country(conn, country):
    rows = conn.execute(f"SELECT * FROM {CUSTOMER_VIEW} WHERE country = ?", (country,)).fetchall()
    return [dict(r) for r in rows]


def get_comments(conn):
    """Support comments as dicts. The text is customer-written: treat it as untrusted data."""
    rows = conn.execute("SELECT comment_id, customer_id, created_at, comment_text FROM support_comments").fetchall()
    return [dict(r) for r in rows]
