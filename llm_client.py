"""Bridge between the LLM (OpenRouter, or Gemini as a fallback) and the expense tracker MCP server."""

import json
import os
from datetime import date
from typing import Any

from dotenv import load_dotenv
from fastmcp import Client
from openai import OpenAI

from server import mcp

load_dotenv()

# Both providers expose an OpenAI-compatible API, so the same tool-calling loop works for either.
# LLM_PROVIDER picks one ("gemini" = Google AI Studio, or "openrouter"); default is Gemini.
PROVIDERS = {
    "openrouter": {
        "key_env": "OPENROUTER_API_KEY",
        "base_url": "https://openrouter.ai/api/v1",
        "model": os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash"),
    },
    "gemini": {
        "key_env": "GEMINI_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"),
    },
}
PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
if PROVIDER not in PROVIDERS:
    raise RuntimeError(f"LLM_PROVIDER must be one of {list(PROVIDERS)}, got {PROVIDER!r}")
MODEL = PROVIDERS[PROVIDER]["model"]
MAX_TOOL_ROUNDS = 5

SYSTEM_PROMPT = """You are an expense tracker assistant. Today's date is {today}.
Use the available tools to add, view, update, delete and summarise expenses.
Always use YYYY-MM-DD dates. Default currency is INR.
If required info (amount or title) is missing, ask the user.
Before deleting anything, confirm with the user.
Keep answers short and friendly."""


def _result_data(result) -> Any:
    """Turn a fastmcp CallToolResult into plain Python data."""
    if result.data is not None:
        return result.data
    if result.structured_content is not None:
        return result.structured_content.get("result", result.structured_content)
    return "\n".join(getattr(c, "text", "") for c in result.content)


async def call_tool(name: str, args: dict | None = None) -> Any:
    """Call an MCP tool directly (used by the Streamlit forms, no LLM)."""
    async with Client(mcp) as client:
        return _result_data(await client.call_tool(name, args or {}))


def _to_openai_tools(mcp_tools) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or "",
                "parameters": t.input_schema,
            },
        }
        for t in mcp_tools
    ]


async def chat(user_message: str, history: list[dict]) -> tuple[str, list[dict]]:
    """Send a user message through the LLM, letting it call MCP tools.
    Returns the assistant reply and the updated history (without the system prompt)."""
    config = PROVIDERS[PROVIDER]
    api_key = os.getenv(config["key_env"])
    if not api_key:
        raise RuntimeError(f"{config['key_env']} is not set. Add it to your .env file.")

    llm = OpenAI(api_key=api_key, base_url=config["base_url"])
    history = history + [{"role": "user", "content": user_message}]
    system = {"role": "system", "content": SYSTEM_PROMPT.format(today=date.today().isoformat())}

    async with Client(mcp) as client:
        tools = _to_openai_tools(await client.list_tools())

        for _ in range(MAX_TOOL_ROUNDS):
            response = llm.chat.completions.create(
                messages=[system] + history,
                model=MODEL,
                tools=tools,
                max_tokens=1024,
            )
            message = response.choices[0].message

            if not message.tool_calls:
                reply = message.content or ""
                history.append({"role": "assistant", "content": reply})
                return reply, history

            history.append({
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                            if isinstance(tc.function.arguments, str)
                            else json.dumps(tc.function.arguments),
                        },
                    }
                    for tc in message.tool_calls
                ],
            })

            for tc in message.tool_calls:
                args = tc.function.arguments
                if isinstance(args, str):
                    args = json.loads(args or "{}")
                result = await client.call_tool(tc.function.name, args, raise_on_error=False)
                content = (
                    "Error: " + "\n".join(getattr(c, "text", "") for c in result.content)
                    if result.is_error
                    else json.dumps(_result_data(result), default=str)
                )
                history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.function.name,
                    "content": content,
                })

    reply = "Sorry, I couldn't finish that request. Please try rephrasing."
    history.append({"role": "assistant", "content": reply})
    return reply, history
