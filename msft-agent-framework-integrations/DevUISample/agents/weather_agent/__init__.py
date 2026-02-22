"""
Weather Agent
=============
Discovered automatically by DevUI via directory-based discovery.

DevUI scans this __init__.py and expects a module-level variable
named ``agent``.

Directory launch::

    devui ./agents --port 8080

"""
from __future__ import annotations

import os
from pathlib import Path

from agent_framework import Agent
from dotenv import load_dotenv

# ── 1. Load env: entity-level first, then parent agents/.env ──────────────
_HERE = Path(__file__).parent
load_dotenv(_HERE / ".env", override=False)          # agent-specific (optional)
load_dotenv(_HERE.parent / ".env", override=False)   # shared agents/.env


# ── 2. Tool definitions ──────────────────────────────────────────────────

def get_current_weather(location: str) -> str:
    """Get the current weather for a location.

    Args:
        location: City name, e.g. "Seattle" or "London, UK".

    Returns:
        A string describing current weather conditions.
    """
    stub: dict[str, str] = {
        "seattle":  "55°F / 13°C, overcast with light drizzle",
        "new york": "62°F / 17°C, partly cloudy",
        "london":   "48°F / 9°C, foggy",
        "tokyo":    "70°F / 21°C, sunny",
        "sydney":   "77°F / 25°C, clear skies",
        "paris":    "52°F / 11°C, cloudy",
        "chicago":  "44°F / 7°C, windy",
        "miami":    "82°F / 28°C, humid and sunny",
    }
    key = location.lower().split(",")[0].strip()
    condition = stub.get(key, "65°F / 18°C, partly cloudy (simulated)")
    return f"Weather in {location}: {condition}"


def get_5_day_forecast(location: str) -> str:
    """Get a 5-day weather forecast for a location.

    Args:
        location: City name, e.g. "London, UK".

    Returns:
        A multi-line string with the forecast.
    """
    return (
        f"5-Day Forecast for {location}:\n"
        "  Day 1: 60°F / 16°C — Sunny\n"
        "  Day 2: 55°F / 13°C — Partly Cloudy\n"
        "  Day 3: 50°F / 10°C — Rainy\n"
        "  Day 4: 58°F / 14°C — Overcast\n"
        "  Day 5: 63°F / 17°C — Sunny\n"
        "(Simulated data — wire a real API for production)"
    )


# ── 3. Build chat client ─────────────────────────────────────────────────
def _build_chat_client():
    """Return the appropriate chat client based on environment config."""
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

    # Falls back to OPENAI_API_KEY env var automatically
    from agent_framework.openai import OpenAIChatClient  # type: ignore[import]

    return OpenAIChatClient(model_id=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))


# ── 4. Agent definition ──────────────────────────────────────────────────
#: DevUI discovers this variable.
agent = Agent(
    _build_chat_client(),
    instructions=(
        "You are a helpful weather assistant. "
        "Use the provided tools to answer questions about current weather and forecasts. "
        "Always include both \u00b0F and \u00b0C in your responses."
    ),
    name="WeatherAgent",
    tools=[get_current_weather, get_5_day_forecast],
)
