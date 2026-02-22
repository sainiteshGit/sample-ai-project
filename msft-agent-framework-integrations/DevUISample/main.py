"""
main.py
==============================================
Registers agents in-memory and launches the DevUI web interface.

Run::

    python main.py

DevUI opens at http://localhost:8080

"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load root .env before importing agents so their _build_chat_client() calls
# can read the credentials.
load_dotenv(Path(__file__).parent / ".env")

# ── Agent imports (each module self-loads its own env as well) ────────────
from agents.weather_agent import agent as weather_agent          # noqa: E402
from agents.assistant_agent import agent as assistant_agent      # noqa: E402

from agent_framework.devui import serve                          # noqa: E402


def main() -> None:
    port = int(os.getenv("DEVUI_PORT", "8080"))
    host = os.getenv("DEVUI_HOST", "127.0.0.1")

    print("║  Microsoft Agent Framework — DevUI Sample        ║")
    print(f"\nRegistered agents:")
    print(f"  • {weather_agent.name}   — weather questions & forecasts")
    print(f"  • {assistant_agent.name} — calculator, datetime, word count")
    print(f"\nStarting DevUI at http://{host}:{port} ...\n")

    serve(
        entities=[weather_agent, assistant_agent],
        host=host,
        port=port,
        auto_open=True,   # open browser automatically
    )


if __name__ == "__main__":
    main()
