"""SQLite helpers for the expense tracker. All SQL lives here."""

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "expenses.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE,
    description  TEXT,
    color        TEXT DEFAULT '#888888',
    budget_limit REAL,
    created_at   TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS expenses (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    title          TEXT NOT NULL,
    amount         REAL NOT NULL CHECK (amount > 0),
    currency       TEXT DEFAULT 'INR',
    category_id    INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    subcategory    TEXT,
    payment_method TEXT DEFAULT 'Cash',
    expense_date   TEXT NOT NULL,
    merchant       TEXT,
    notes          TEXT,
    tags           TEXT,
    is_recurring   INTEGER DEFAULT 0,
    created_at     TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at     TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_expenses_date     ON expenses(expense_date);
CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category_id);

CREATE TABLE IF NOT EXISTS chats (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    messages   TEXT NOT NULL DEFAULT '[]',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

DEFAULT_CATEGORIES = [
    ("Food", "#e4572e"),
    ("Groceries", "#76b041"),
    ("Transport", "#17bebb"),
    ("Rent", "#7b2cbf"),
    ("Utilities", "#ffc914"),
    ("Shopping", "#ff70a6"),
    ("Entertainment", "#4361ee"),
    ("Health", "#06d6a0"),
    ("Education", "#118ab2"),
    ("Travel", "#f77f00"),
    ("Bills & Subscriptions", "#8d99ae"),
    ("Other", "#888888"),
]

EXPENSE_FIELDS = {
    "title", "amount", "currency", "category_id", "subcategory", "payment_method",
    "expense_date", "merchant", "notes", "tags", "is_recurring",
}
CATEGORY_FIELDS = {"name", "description", "color", "budget_limit"}

EXPENSE_SELECT = """
SELECT e.*, c.name AS category
FROM expenses e
LEFT JOIN categories c ON c.id = e.category_id
"""


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row else None


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        conn.executemany(
            "INSERT OR IGNORE INTO categories (name, color) VALUES (?, ?)",
            DEFAULT_CATEGORIES,
        )


# ---------- categories ----------

def fetch_categories() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM categories ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def fetch_category(category_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
    return row_to_dict(row)


def get_or_create_category_id(name: str) -> int:
    """Look up a category by name (case-insensitive), creating it if missing."""
    name = name.strip() or "Other"
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM categories WHERE name = ? COLLATE NOCASE", (name,)
        ).fetchone()
        if row:
            return row["id"]
        return conn.execute("INSERT INTO categories (name) VALUES (?)", (name,)).lastrowid


def insert_category(data: dict) -> dict:
    cols = [k for k in data if k in CATEGORY_FIELDS]
    sql = f"INSERT INTO categories ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
    with get_conn() as conn:
        new_id = conn.execute(sql, [data[c] for c in cols]).lastrowid
    return fetch_category(new_id)


def update_category(category_id: int, data: dict) -> dict | None:
    cols = [k for k in data if k in CATEGORY_FIELDS]
    if cols:
        sql = f"UPDATE categories SET {', '.join(f'{c} = ?' for c in cols)} WHERE id = ?"
        with get_conn() as conn:
            conn.execute(sql, [data[c] for c in cols] + [category_id])
    return fetch_category(category_id)


def delete_category(category_id: int) -> bool:
    with get_conn() as conn:
        return conn.execute("DELETE FROM categories WHERE id = ?", (category_id,)).rowcount > 0


# ---------- expenses ----------

def fetch_expense(expense_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(EXPENSE_SELECT + " WHERE e.id = ?", (expense_id,)).fetchone()
    return row_to_dict(row)


def fetch_expenses(
    start_date: str | None = None,
    end_date: str | None = None,
    category: str | None = None,
    payment_method: str | None = None,
    search: str | None = None,
    limit: int = 50,
) -> list[dict]:
    where, params = [], []
    if start_date:
        where.append("e.expense_date >= ?")
        params.append(start_date)
    if end_date:
        where.append("e.expense_date <= ?")
        params.append(end_date)
    if category:
        where.append("c.name = ? COLLATE NOCASE")
        params.append(category)
    if payment_method:
        where.append("e.payment_method = ? COLLATE NOCASE")
        params.append(payment_method)
    if search:
        where.append("(e.title LIKE ? OR e.merchant LIKE ? OR e.notes LIKE ? OR e.tags LIKE ?)")
        params.extend([f"%{search}%"] * 4)

    sql = EXPENSE_SELECT
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY e.expense_date DESC, e.id DESC LIMIT ?"
    params.append(limit)

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def insert_expense(data: dict) -> dict:
    cols = [k for k in data if k in EXPENSE_FIELDS]
    sql = f"INSERT INTO expenses ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
    with get_conn() as conn:
        new_id = conn.execute(sql, [data[c] for c in cols]).lastrowid
    return fetch_expense(new_id)


def update_expense(expense_id: int, data: dict) -> dict | None:
    cols = [k for k in data if k in EXPENSE_FIELDS]
    if cols:
        sets = ", ".join(f"{c} = ?" for c in cols) + ", updated_at = CURRENT_TIMESTAMP"
        with get_conn() as conn:
            conn.execute(
                f"UPDATE expenses SET {sets} WHERE id = ?",
                [data[c] for c in cols] + [expense_id],
            )
    return fetch_expense(expense_id)


def delete_expense(expense_id: int) -> bool:
    with get_conn() as conn:
        return conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,)).rowcount > 0


# ---------- reports ----------

def summarize(start_date: str | None = None, end_date: str | None = None) -> dict:
    where, params = [], []
    if start_date:
        where.append("e.expense_date >= ?")
        params.append(start_date)
    if end_date:
        where.append("e.expense_date <= ?")
        params.append(end_date)
    clause = (" WHERE " + " AND ".join(where)) if where else ""

    with get_conn() as conn:
        totals = conn.execute(
            f"SELECT COALESCE(SUM(e.amount), 0) AS total, COUNT(*) AS count FROM expenses e{clause}",
            params,
        ).fetchone()
        by_category = conn.execute(
            f"""SELECT COALESCE(c.name, 'Uncategorized') AS category,
                       SUM(e.amount) AS total, COUNT(*) AS count
                FROM expenses e LEFT JOIN categories c ON c.id = e.category_id
                {clause}
                GROUP BY category ORDER BY total DESC""",
            params,
        ).fetchall()
        by_date = conn.execute(
            f"""SELECT e.expense_date AS date, SUM(e.amount) AS total
                FROM expenses e{clause}
                GROUP BY e.expense_date ORDER BY e.expense_date""",
            params,
        ).fetchall()

    return {
        "total": totals["total"],
        "count": totals["count"],
        "by_category": [dict(r) for r in by_category],
        "by_date": [dict(r) for r in by_date],
    }


def budget_report(month_prefix: str) -> list[dict]:
    """Spend per category for a month ('YYYY-MM') compared with each budget_limit."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT c.name AS category, c.budget_limit,
                      COALESCE(SUM(e.amount), 0) AS spent
               FROM categories c
               LEFT JOIN expenses e
                 ON e.category_id = c.id AND substr(e.expense_date, 1, 7) = ?
               GROUP BY c.id
               HAVING spent > 0 OR c.budget_limit IS NOT NULL
               ORDER BY spent DESC""",
            (month_prefix,),
        ).fetchall()
    report = []
    for r in rows:
        item = dict(r)
        limit = item["budget_limit"]
        item["remaining"] = None if limit is None else round(limit - item["spent"], 2)
        item["over_budget"] = limit is not None and item["spent"] > limit
        report.append(item)
    return report


# ---------- chat history (used by the Streamlit UI only) ----------

def fetch_chats() -> list[dict]:
    """All chats, newest first, without their messages."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, title, updated_at FROM chats ORDER BY updated_at DESC, id DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def fetch_chat_messages(chat_id: int) -> list[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT messages FROM chats WHERE id = ?", (chat_id,)).fetchone()
    return json.loads(row["messages"]) if row else []


def save_chat(chat_id: int | None, title: str, messages: list[dict]) -> int:
    """Create (chat_id=None) or update a chat. Returns its id."""
    payload = json.dumps(messages, default=str)
    with get_conn() as conn:
        if chat_id is None:
            return conn.execute(
                "INSERT INTO chats (title, messages) VALUES (?, ?)", (title, payload)
            ).lastrowid
        conn.execute(
            "UPDATE chats SET messages = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (payload, chat_id),
        )
        return chat_id


def delete_chat(chat_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
