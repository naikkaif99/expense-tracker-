# Expense Tracker

Expense tracker built on an MCP server (FastMCP + SQLite), with Google Gemini (AI Studio) or OpenRouter for
natural-language chat and a Streamlit UI. See [ARCHITECTURE.md](ARCHITECTURE.md) for the design.

## Setup

```bash
uv sync
cp .env.example .env   # then put your Google AI Studio key in .env
```

Get a Google AI Studio key at https://aistudio.google.com/apikey and set `GEMINI_API_KEY`.
`GEMINI_MODEL` can be any Gemini model that supports function calling (default `gemini-2.5-flash-lite`; the free tier has a small daily request limit per model).

To use OpenRouter instead, set `LLM_PROVIDER=openrouter` and `OPENROUTER_API_KEY`
(key from https://openrouter.ai/keys). `OPENROUTER_MODEL` must support tool calling.

## Run

```bash
uv run streamlit run app.py
```

The SQLite database `expenses.db` is created automatically with default categories.

## Use the MCP server on its own

```bash
uv run python server.py         # stdio MCP server (e.g. for Claude Desktop)
uv run fastmcp dev server.py    # inspect and try tools in MCP Inspector
```

## Files

| File            | Purpose                                         |
|-----------------|-------------------------------------------------|
| `db.py`         | SQLite schema, seed categories, all SQL queries |
| `server.py`     | FastMCP server with CRUD + report tools         |
| `llm_client.py` | LLM tool-calling loop + MCP client              |
| `app.py`        | Streamlit UI (Chat, Expenses, Categories, Dashboard) |
