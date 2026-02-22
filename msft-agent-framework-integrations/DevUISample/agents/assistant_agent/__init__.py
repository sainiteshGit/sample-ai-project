"""
General Assistant Agent
=======================
Discovered automatically by DevUI via directory-based discovery.

DevUI scans this __init__.py and expects a module-level variable
named ``agent``.

"""
from __future__ import annotations

import datetime
import os
from pathlib import Path

from agent_framework import Agent
from dotenv import load_dotenv

# ── 1. Load env ───────────────────────────────────────────────────────────
_HERE = Path(__file__).parent
load_dotenv(_HERE / ".env", override=False)
load_dotenv(_HERE.parent / ".env", override=False)


# ── 2. Tool definitions ──────────────────────────────────────────────────

_SAFE_CHARS = frozenset("0123456789+-*/()., ")


def calculate(expression: str) -> str:
    """Evaluate a simple arithmetic expression.

    Args:
        expression: A math expression, e.g. ``"(2 + 3) * 4"`` or ``"10 / 2.5"``.

    Returns:
        The result as a string, or an error message.
    """
    if "**" in expression or not all(c in _SAFE_CHARS for c in expression):
        return (
            f"Unsafe expression '{expression}'. "
            "Only basic arithmetic operators (+, -, *, /) and parentheses are allowed."
        )
    try:
        result = eval(expression, {"__builtins__": {}})  # noqa: S307
        return f"Result of '{expression}' = {result}"
    except Exception as exc:  # noqa: BLE001
        return f"Could not evaluate '{expression}': {exc}"


def get_current_datetime() -> str:
    """Return the current UTC date and time."""
    now = datetime.datetime.now(datetime.timezone.utc)
    return f"Current UTC date and time: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC"


def word_count(text: str) -> str:
    """Count the number of words in a piece of text.

    Args:
        text: The text to analyse.

    Returns:
        Word and character counts.
    """
    words = len(text.split())
    chars = len(text)
    return f"Word count: {words} words, {chars} characters."


# ── 3. Build chat client ─────────────────────────────────────────────────

def _build_chat_client():
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_api_key  = os.getenv("AZURE_OPENAI_API_KEY")
    deployment     = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")

    if azure_endpoint:
        from agent_framework.azure import AzureOpenAIChatClient  # type: ignore[import]

        return AzureOpenAIChatClient(
            endpoint=azure_endpoint,
            api_key=azure_api_key,
            deployment_name=deployment,
        )

    from agent_framework.openai import OpenAIChatClient  # type: ignore[import]

    return OpenAIChatClient(model_id=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))


# ── 4. Agent definition ──────────────────────────────────────────────────

#: DevUI discovers this variable.
agent = Agent(
    _build_chat_client(),
    instructions=(
        "You are a general-purpose assistant. "
        "Help users with questions, calculations, code explanations, and more. "
        "Use the provided tools when they are relevant."
    ),
    name="AssistantAgent",
    tools=[calculate, get_current_datetime, word_count],
)
