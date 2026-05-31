"""
Agentic Sandbox — Crawl Phase
=============================

Claude/Codex-style live code execution UI in the terminal, powered by:
  - Microsoft Agent Framework (MAF) Python SDK
  - Azure OpenAI Responses API
  - Built-in code interpreter tool (provider-hosted Python sandbox)

Run:
    cp .env.template .env  # then edit values
    pip install -r requirements.txt
    python cli.py "Plot a sine wave and save it as sine.png"
"""

from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from agent_framework.azure import AzureOpenAIResponsesClient

load_dotenv()

console = Console()


# ---------------------------------------------------------------------------
# UI helpers — Claude/Codex-style step rendering
# ---------------------------------------------------------------------------

def render_user(prompt: str) -> None:
    console.print(Panel(Text(prompt, style="white"), title="[bold cyan]You", border_style="cyan"))


def render_assistant_text(text: str) -> None:
    if not text.strip():
        return
    console.print(Panel(Text(text), title="[bold green]Assistant", border_style="green"))


def render_code(code: str) -> None:
    body = Syntax(code, "python", theme="monokai", line_numbers=True, word_wrap=True)
    console.print(Panel(body, title="[bold yellow]⚙  Running Python (sandbox)", border_style="yellow"))


def render_result(text: str) -> None:
    if not text:
        text = "(no output)"
    if len(text) > 4000:
        text = text[:4000] + "\n…[truncated]"
    console.print(Panel(Text(text), title="[bold magenta]✓ Sandbox result", border_style="magenta"))


# ---------------------------------------------------------------------------
# Streaming event handler
# ---------------------------------------------------------------------------

async def stream_agent(agent, prompt: str) -> None:
    """
    Render Claude/Codex-style step panels from a MAF streamed run.

    Content shapes from Azure OpenAI Responses API (via MAF):
      - type='text'                          → assistant text delta
      - type='code_interpreter_tool_call'    → code delta / done events
                                               (raw_representation carries
                                                ResponseCodeInterpreterCallCodeDeltaEvent
                                                or ResponseCodeInterpreterCallCodeDoneEvent)
      - type='code_interpreter_tool_result'  → status / outputs container
      - type='usage'                         → final token usage
    """
    render_user(prompt)

    assistant_buf: list[str] = []
    code_by_call: dict[str, str] = {}
    rendered_code: set[str] = set()
    rendered_result: set[str] = set()

    async for update in agent.run(prompt, stream=True):
        for content in update.contents or []:
            ctype = getattr(content, "type", None)
            raw = getattr(content, "raw_representation", None)
            raw_name = type(raw).__name__ if raw is not None else ""

            if ctype == "text":
                delta = getattr(content, "text", None) or ""
                if delta:
                    assistant_buf.append(delta)

            elif ctype == "code_interpreter_tool_call":
                call_id = getattr(content, "call_id", None) or ""

                if raw_name == "ResponseCodeInterpreterCallCodeDeltaEvent":
                    delta = getattr(raw, "delta", "") or ""
                    code_by_call[call_id] = code_by_call.get(call_id, "") + delta

                elif raw_name == "ResponseCodeInterpreterCallCodeDoneEvent":
                    code = getattr(raw, "code", None) or code_by_call.get(call_id, "")
                    if call_id not in rendered_code and code:
                        if assistant_buf:
                            render_assistant_text("".join(assistant_buf))
                            assistant_buf.clear()
                        render_code(code)
                        rendered_code.add(call_id)

            elif ctype == "code_interpreter_tool_result":
                call_id = getattr(content, "call_id", None) or ""
                status = None
                outputs = None
                if raw is not None:
                    status = getattr(raw, "status", None)
                    outputs = getattr(raw, "outputs", None)
                if status in ("completed", "failed") and call_id not in rendered_result:
                    text_parts: list[str] = []
                    for o in outputs or []:
                        for attr in ("logs", "text", "url"):
                            v = getattr(o, attr, None)
                            if v:
                                text_parts.append(str(v))
                    render_result("\n".join(text_parts))
                    rendered_result.add(call_id)

    if assistant_buf:
        render_assistant_text("".join(assistant_buf))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build_agent():
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT")
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")

    if not all([endpoint, api_key, deployment]):
        console.print("[red]ERROR:[/red] Set AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT in .env")
        sys.exit(1)

    client = AzureOpenAIResponsesClient(
        endpoint=endpoint,
        api_key=api_key,
        deployment_name=deployment,
        api_version=api_version,
    )

    return client.as_agent(
        name="SandboxAgent",
        instructions=(
            "You are an agentic assistant with access to a Python code interpreter "
            "sandbox. For any computation, data analysis, plotting, math, or file "
            "generation task, WRITE AND EXECUTE Python code using the code "
            "interpreter tool rather than answering from memory. Briefly state what "
            "you will do, then run the code, then summarise the result."
        ),
        tools=[client.get_code_interpreter_tool()],
    )


async def main() -> None:
    if len(sys.argv) < 2:
        console.print("[yellow]Usage:[/yellow] python cli.py \"<your prompt>\"")
        console.print("[dim]Example:[/dim] python cli.py \"Compute the 50th Fibonacci number\"")
        sys.exit(2)

    prompt = " ".join(sys.argv[1:])
    agent = build_agent()
    await stream_agent(agent, prompt)


if __name__ == "__main__":
    asyncio.run(main())
