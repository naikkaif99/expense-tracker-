# Expense Tracker – MCP Server Architecture

A simple expense tracker built around an **MCP server** (FastMCP) backed by **SQLite**.
A **Hugging Face LLM** acts as the MCP client's "brain", and **Streamlit** provides the UI.

> Status: implemented.

---

## 1. High-Level Overview

```
┌──────────────────────────────────────────────────────────────┐
│                     Streamlit UI (app.py)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │  Chat tab    │  │ Expenses tab │  │ Dashboard tab      │  │
│  │ (natural     │  │ (forms/table │  │ (charts, totals)   │  │
│  │  language)   │  │  for CRUD)   │  │                    │  │
│  └──────┬───────┘  └──────┬───────┘  └─────────┬──────────┘  │
└─────────┼─────────────────┼────────────────────┼─────────────┘
          │                 │                    │
          ▼                 │ direct tool calls  │
┌────────────────────┐      │                    │
│ LLM Client         │      │                    │
│ (llm_client.py)    │      │                    │
│ Hugging Face       │      │                    │
│ InferenceClient    │      │                    │
│ + tool calling     │      │                    │
└─────────┬──────────┘      │                    │
          │ tool calls      │                    │
          ▼                 ▼                    ▼
┌──────────────────────────────────────────────────────────────┐
│           FastMCP Client  (fastmcp.Client)                   │
└──────────────────────────────┬───────────────────────────────┘
                               │ MCP protocol (in-memory)
                               ▼
┌──────────────────────────────────────────────────────────────┐
│            FastMCP Server (server.py)                        │
│   Tools: add_expense, list_expenses, update_expense, ...     │
└──────────────────────────────┬───────────────────────────────┘
                               │ sqlite3
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                SQLite database (expenses.db)                 │
│          tables: categories, expenses                        │
└──────────────────────────────────────────────────────────────┘
```

**Two ways to use the app:**

1. **Chat** – user types "I spent 250 on lunch today with UPI". The HF LLM decides which
   MCP tool to call (`add_expense`), the client executes it, and the LLM replies with the result.
2. **Forms / Dashboard** – Streamlit calls the MCP tools directly (no LLM) for normal CRUD
   and reporting. Fast, predictable, no token cost.

Both paths go through the **same MCP server**, so all business logic lives in one place.

---

## 2. Tech Stack

| Layer        | Choice                                     | Why                                  |
|--------------|--------------------------------------------|--------------------------------------|
| Language     | Python 3.14 (managed with `uv`)            | Already set up in `pyproject.toml`   |
| MCP server   | `fastmcp`                                  | Decorator-based tools, minimal code  |
| Database     | `sqlite3` (standard library)               | Zero setup, single file              |
| LLM          | Hugging Face Inference API (`huggingface_hub.InferenceClient`) | Free tier, OpenAI-style tool calling |
| UI           | `streamlit`                                | Quick Python-only UI                 |
| Config       | `python-dotenv`                            | Load `HF_TOKEN` from `.env`          |
| Charts       | `pandas` + Streamlit built-in charts       | No extra chart library needed        |

**Dependencies to add later:**

```bash
uv add fastmcp huggingface_hub streamlit python-dotenv pandas
```

---

## 3. Project Structure

```
expense-tracker/
├── ARCHITECTURE.md      # this file
├── README.md
├── pyproject.toml
├── .env                 # HF_TOKEN, HF_MODEL (not committed)
├── .env.example         # template for .env
├── .gitignore           # add .env and *.db
│
├── db.py                # SQLite connection, schema creation, seed categories
├── server.py            # FastMCP server – all MCP tools (CRUD + summary)
├── llm_client.py        # Hugging Face LLM + fastmcp Client bridge (chat loop)
├── app.py               # Streamlit UI
│
└── expenses.db          # created automatically on first run
```


---

## 4. Database Design (SQLite)

### 4.1 `categories`

| Column        | Type    | Constraints                          | Description                          |
|---------------|---------|--------------------------------------|--------------------------------------|
| `id`          | INTEGER | PRIMARY KEY AUTOINCREMENT            | Category ID                          |
| `name`        | TEXT    | NOT NULL, UNIQUE                     | e.g. Food, Travel, Rent              |
| `description` | TEXT    |                                      | Optional details                     |
| `color`       | TEXT    | DEFAULT '#888888'                    | Used in UI charts                    |
| `budget_limit`| REAL    | DEFAULT NULL                         | Optional monthly budget for category |
| `created_at`  | TEXT    | DEFAULT CURRENT_TIMESTAMP            | ISO timestamp                        |

### 4.2 `expenses`

| Column           | Type    | Constraints                                   | Description                                |
|------------------|---------|-----------------------------------------------|--------------------------------------------|
| `id`             | INTEGER | PRIMARY KEY AUTOINCREMENT                     | Expense ID                                 |
| `title`          | TEXT    | NOT NULL                                      | Short label, e.g. "Lunch at cafe"          |
| `amount`         | REAL    | NOT NULL, CHECK (amount > 0)                  | Expense amount                             |
| `currency`       | TEXT    | DEFAULT 'INR'                                 | Currency code                              |
| `category_id`    | INTEGER | REFERENCES categories(id) ON DELETE SET NULL  | Link to category                           |
| `subcategory`    | TEXT    |                                               | Free text, e.g. "Groceries" under Food     |
| `payment_method` | TEXT    | DEFAULT 'Cash'                                | Cash / UPI / Card / Net Banking / Other    |
| `expense_date`   | TEXT    | NOT NULL                                      | `YYYY-MM-DD`                               |
| `merchant`       | TEXT    |                                               | Where the money was spent                  |
| `notes`          | TEXT    |                                               | Any extra info                             |
| `tags`           | TEXT    |                                               | Comma-separated, e.g. "office,reimbursable"|
| `is_recurring`   | INTEGER | DEFAULT 0 (0/1)                               | Monthly bills, subscriptions               |
| `created_at`     | TEXT    | DEFAULT CURRENT_TIMESTAMP                     | Row creation time                          |
| `updated_at`     | TEXT    | DEFAULT CURRENT_TIMESTAMP                     | Set on every update                        |

### 4.3 Schema SQL

```sql
PRAGMA foreign_keys = ON;

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
```

### 4.4 Default Categories (seeded on first run)

Food, Groceries, Transport, Rent, Utilities, Shopping, Entertainment,
Health, Education, Travel, Bills & Subscriptions, Other.

---

## 5. MCP Server (`server.py`)

Built with `FastMCP`. Each function decorated with `@mcp.tool` becomes a tool the LLM
(or Streamlit) can call. All tools return plain dicts/lists (JSON-serialisable).

### 5.1 Skeleton (for reference only)

```python
from fastmcp import FastMCP
import db

mcp = FastMCP("Expense Tracker")

@mcp.tool
def add_expense(title: str, amount: float, expense_date: str,
                category: str = "Other", payment_method: str = "Cash",
                subcategory: str = "", merchant: str = "",
                notes: str = "", tags: str = "", currency: str = "INR") -> dict:
    """Add a new expense. Date format: YYYY-MM-DD."""
    ...

if __name__ == "__main__":
    db.init_db()
    mcp.run()          # stdio transport by default
```

### 5.2 Tools

**Expense CRUD**

| Tool               | Params                                                                 | Returns                 |
|--------------------|------------------------------------------------------------------------|-------------------------|
| `add_expense`      | title, amount, expense_date, category, payment_method, subcategory, merchant, notes, tags, currency, is_recurring | created expense         |
| `get_expense`      | expense_id                                                             | single expense          |
| `list_expenses`    | start_date?, end_date?, category?, payment_method?, search?, limit=50  | list of expenses        |
| `update_expense`   | expense_id + any field to change (all optional)                        | updated expense         |
| `delete_expense`   | expense_id                                                             | `{"deleted": true}`     |

**Category CRUD**

| Tool               | Params                                       | Returns                 |
|--------------------|----------------------------------------------|-------------------------|
| `add_category`     | name, description?, color?, budget_limit?    | created category        |
| `list_categories`  | –                                            | list of categories      |
| `update_category`  | category_id + fields to change               | updated category        |
| `delete_category`  | category_id                                  | `{"deleted": true}`     |

**Reports**

| Tool                    | Params                         | Returns                                    |
|-------------------------|--------------------------------|--------------------------------------------|
| `summarize_expenses`    | start_date?, end_date?         | total, count, total per category           |
| `monthly_summary`       | year, month                    | totals per category vs. `budget_limit`     |

**Design rules**
- Category is passed by **name** in `add_expense`/`update_expense` (easier for the LLM);
  the server looks up or creates the `category_id`.
- `update_expense` only updates the fields that are provided and sets `updated_at`.
- Validation (amount > 0, valid date) happens in the tool; errors are raised as
  `ValueError` so FastMCP returns a clean error to the client.
- All SQL lives in `db.py`; tools stay short.

### 5.3 Optional MCP Resource

```
expenses://categories   -> list of categories (read-only context for the LLM)
```

---

## 6. Database Helper (`db.py`)

Small module with plain functions, no ORM:

- `get_conn()` – returns `sqlite3.connect("expenses.db")` with `row_factory = sqlite3.Row`
  and `PRAGMA foreign_keys = ON`.
- `init_db()` – runs the schema SQL and seeds default categories.
- `row_to_dict(row)` – converts `sqlite3.Row` to `dict`.
- One function per operation used by the tools (`insert_expense`, `fetch_expenses`, ...).

Use parameterised queries (`?`) everywhere — never string-format SQL.

---

## 7. LLM Client (`llm_client.py`)

Connects the **Hugging Face LLM** to the **MCP server** using the tool-calling loop.

### 7.1 Config (`.env`)

```
HF_TOKEN=hf_xxxxxxxxxxxxxxxxx
HF_MODEL=Qwen/Qwen2.5-72B-Instruct
```

Any HF model that supports tool/function calling via the Inference API works
(e.g. `Qwen/Qwen2.5-72B-Instruct`, `meta-llama/Llama-3.1-8B-Instruct`). Keep it configurable.

### 7.2 Flow

```
user message
     │
     ▼
1. fastmcp.Client("server.py")  ──► list_tools()
2. Convert MCP tools → HF/OpenAI tool schema
      {"type": "function", "function": {name, description, parameters: inputSchema}}
3. InferenceClient.chat_completion(model, messages, tools=tools)
     │
     ├── no tool_calls  ──► return assistant text
     │
     └── tool_calls     ──► for each call:
                               result = client.call_tool(name, json.loads(arguments))
                               append {"role": "tool", "tool_call_id": ..., "content": result}
                            loop back to step 3 (max ~5 iterations)
```

### 7.3 System Prompt

```
You are an expense tracker assistant. Today's date is {today}.
Use the available tools to add, view, update, delete and summarise expenses.
Always use YYYY-MM-DD dates. Default currency is INR.
If required info (amount or title) is missing, ask the user.
Before deleting anything, confirm with the user.
```

### 7.4 Public Function

```python
async def chat(user_message: str, history: list[dict]) -> tuple[str, list[dict]]:
    """Returns assistant reply and updated history."""
```

Plus a thin helper used by the Streamlit forms (no LLM):

```python
async def call_tool(name: str, args: dict) -> Any:
    async with Client(mcp) as client:      # mcp imported from server.py
        return (await client.call_tool(name, args)).data
```

The client connects to the server **in-memory** (`Client(mcp)`) instead of spawning
`server.py` over stdio for every call — same MCP protocol, but no ~2s process start-up per
request. `server.py` still runs standalone over stdio for external MCP clients.

Streamlit is synchronous, so wrap calls with `asyncio.run(...)`.

---

## 8. Streamlit UI (`app.py`)

Run with: `uv run streamlit run app.py`

### 8.1 Layout

**Sidebar**
- Date range filter
- Category filter
- HF model name (read from `.env`, display only)

**Tab 1 – 💬 Chat**
- `st.chat_message` / `st.chat_input`
- History kept in `st.session_state.messages`
- Calls `llm_client.chat(...)`
- Example prompts: "Add 500 for groceries yesterday via card", "How much did I spend on food this month?"

**Tab 2 – ➕ Add / Edit Expenses**
- `st.form` with: title, amount, currency, date, category (selectbox from `list_categories`),
  subcategory, payment method, merchant, tags, notes, recurring checkbox
- Submit → `call_tool("add_expense", {...})`
- Table of expenses (`st.dataframe`) from `list_expenses`
- Select a row → edit form (`update_expense`) or delete button (`delete_expense`, with confirm)

**Tab 3 – 🗂️ Categories**
- List, add, edit, delete categories (name, color, budget limit)

**Tab 4 – 📊 Dashboard**
- Metrics: total spent, number of expenses, top category (`st.metric`)
- Bar chart: spend per category (`summarize_expenses`)
- Line chart: spend per day/month
- Budget vs. actual per category (`monthly_summary`)

### 8.2 State

| Key                          | Purpose                   |
|------------------------------|---------------------------|
| `st.session_state.messages`  | chat history              |
| `st.session_state.edit_id`   | expense currently edited  |

---

## 9. Request Flow Examples

**A. Chat: "I spent 250 on lunch today with UPI"**
1. Streamlit → `llm_client.chat()`
2. LLM returns tool call `add_expense(title="Lunch", amount=250, category="Food", payment_method="UPI", expense_date="2026-10-17")`
3. fastmcp Client → MCP server → `INSERT INTO expenses ...`
4. Result goes back to LLM → "Added ₹250 for Lunch under Food (UPI)."

**B. Form: delete expense #12**
1. Streamlit button → `call_tool("delete_expense", {"expense_id": 12})`
2. MCP server → `DELETE FROM expenses WHERE id = 12`
3. UI refreshes table (`st.rerun()`)

---

## 10. Running the App (once implemented)

```bash
uv sync
# copy .env.example to .env with HF_TOKEN and HF_MODEL
uv run python server.py           # optional: test the server standalone
uv run fastmcp dev server.py      # optional: inspect tools in MCP Inspector
uv run streamlit run app.py       # main app (talks to the server in-memory)
```

The MCP server can also be plugged into other MCP clients (e.g. Claude Desktop) since it is a
standard stdio MCP server.

---

## 11. Implementation Order

1. `db.py` – schema + seed categories
2. `server.py` – expense & category CRUD tools, then report tools
3. Test tools with `fastmcp dev server.py`
4. `llm_client.py` – HF tool-calling loop
5. `app.py` – Forms & Dashboard tabs first, then Chat tab
6. Update `README.md` and `.gitignore` (`.env`, `*.db`)

---

## 12. Keep It Simple – Non-Goals (for now)

- No authentication / multi-user support
- No ORM (plain `sqlite3`)
- No separate REST API — MCP server is the only backend
- No async database driver
- No Docker
