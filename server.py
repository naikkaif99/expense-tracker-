"""FastMCP server exposing expense tracker tools backed by SQLite."""

from datetime import date

from fastmcp import FastMCP

import db

mcp = FastMCP(
    "Expense Tracker",
    instructions="Track personal expenses: add, list, update, delete and summarise them.",
)

PAYMENT_METHODS = ["Cash", "UPI", "Card", "Net Banking", "Other"]


def _check_date(value: str) -> str:
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"Invalid date '{value}'. Use YYYY-MM-DD.")
    return value


def _check_amount(value: float) -> float:
    if value <= 0:
        raise ValueError("Amount must be greater than 0.")
    return value


# ---------- expenses ----------

@mcp.tool
def add_expense(
    title: str,
    amount: float,
    expense_date: str,
    category: str = "Other",
    payment_method: str = "Cash",
    subcategory: str = "",
    merchant: str = "",
    notes: str = "",
    tags: str = "",
    currency: str = "INR",
    is_recurring: bool = False,
) -> dict:
    """Add a new expense. expense_date must be YYYY-MM-DD.
    payment_method is one of: Cash, UPI, Card, Net Banking, Other.
    tags is a comma-separated string."""
    return db.insert_expense({
        "title": title,
        "amount": _check_amount(amount),
        "expense_date": _check_date(expense_date),
        "category_id": db.get_or_create_category_id(category),
        "payment_method": payment_method,
        "subcategory": subcategory,
        "merchant": merchant,
        "notes": notes,
        "tags": tags,
        "currency": currency,
        "is_recurring": int(is_recurring),
    })


@mcp.tool
def get_expense(expense_id: int) -> dict:
    """Get a single expense by its id."""
    expense = db.fetch_expense(expense_id)
    if not expense:
        raise ValueError(f"Expense {expense_id} not found.")
    return expense


@mcp.tool
def list_expenses(
    start_date: str | None = None,
    end_date: str | None = None,
    category: str | None = None,
    payment_method: str | None = None,
    search: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List expenses, newest first. All filters are optional.
    Dates are YYYY-MM-DD (inclusive). search matches title, merchant, notes and tags."""
    if start_date:
        _check_date(start_date)
    if end_date:
        _check_date(end_date)
    return db.fetch_expenses(start_date, end_date, category, payment_method, search, limit)


@mcp.tool
def update_expense(
    expense_id: int,
    title: str | None = None,
    amount: float | None = None,
    expense_date: str | None = None,
    category: str | None = None,
    payment_method: str | None = None,
    subcategory: str | None = None,
    merchant: str | None = None,
    notes: str | None = None,
    tags: str | None = None,
    currency: str | None = None,
    is_recurring: bool | None = None,
) -> dict:
    """Update an expense. Only the fields you pass are changed."""
    if not db.fetch_expense(expense_id):
        raise ValueError(f"Expense {expense_id} not found.")

    changes = {
        "title": title,
        "amount": _check_amount(amount) if amount is not None else None,
        "expense_date": _check_date(expense_date) if expense_date else None,
        "category_id": db.get_or_create_category_id(category) if category else None,
        "payment_method": payment_method,
        "subcategory": subcategory,
        "merchant": merchant,
        "notes": notes,
        "tags": tags,
        "currency": currency,
        "is_recurring": int(is_recurring) if is_recurring is not None else None,
    }
    return db.update_expense(expense_id, {k: v for k, v in changes.items() if v is not None})


@mcp.tool
def delete_expense(expense_id: int) -> dict:
    """Delete an expense by its id."""
    if not db.delete_expense(expense_id):
        raise ValueError(f"Expense {expense_id} not found.")
    return {"deleted": True, "expense_id": expense_id}


# ---------- categories ----------

@mcp.tool
def list_categories() -> list[dict]:
    """List all expense categories."""
    return db.fetch_categories()


@mcp.tool
def add_category(
    name: str,
    description: str = "",
    color: str = "#888888",
    budget_limit: float | None = None,
) -> dict:
    """Create a new category. budget_limit is an optional monthly budget."""
    return db.insert_category({
        "name": name.strip(),
        "description": description,
        "color": color,
        "budget_limit": budget_limit,
    })


@mcp.tool
def update_category(
    category_id: int,
    name: str | None = None,
    description: str | None = None,
    color: str | None = None,
    budget_limit: float | None = None,
) -> dict:
    """Update a category. Only the fields you pass are changed."""
    if not db.fetch_category(category_id):
        raise ValueError(f"Category {category_id} not found.")
    changes = {"name": name, "description": description, "color": color, "budget_limit": budget_limit}
    return db.update_category(category_id, {k: v for k, v in changes.items() if v is not None})


@mcp.tool
def delete_category(category_id: int) -> dict:
    """Delete a category. Its expenses become uncategorized."""
    if not db.delete_category(category_id):
        raise ValueError(f"Category {category_id} not found.")
    return {"deleted": True, "category_id": category_id}


# ---------- reports ----------

@mcp.tool
def summarize_expenses(start_date: str | None = None, end_date: str | None = None) -> dict:
    """Total spend, number of expenses, spend per category and per day
    for an optional date range (YYYY-MM-DD, inclusive)."""
    return db.summarize(start_date, end_date)


@mcp.tool
def monthly_summary(year: int, month: int) -> list[dict]:
    """Spend per category for a given month compared with each category's budget_limit."""
    if not 1 <= month <= 12:
        raise ValueError("month must be between 1 and 12.")
    return db.budget_report(f"{year:04d}-{month:02d}")


db.init_db()

if __name__ == "__main__":
    mcp.run(show_banner=False)
