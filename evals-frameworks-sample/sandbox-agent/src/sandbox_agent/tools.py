"""Tools the model can call. Each tool executes inside the run's sandbox."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from sandbox_agent.sandbox import SandboxSession

MAX_OUTPUT_CHARS = 4000


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    run: Callable[[SandboxSession, dict[str, Any]], str]

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def _clip(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + f"\n...[truncated {len(text) - MAX_OUTPUT_CHARS} chars]"


def _run_shell(sb: SandboxSession, args: dict[str, Any]) -> str:
    result = sb.exec(args["command"], working_directory=args.get("working_directory"))
    return json.dumps(
        {
            "exit_code": result.exit_code,
            "stdout": _clip(result.stdout or ""),
            "stderr": _clip(result.stderr or ""),
        }
    )


def _read_file(sb: SandboxSession, args: dict[str, Any]) -> str:
    return _clip(sb.read_file(args["path"]).decode("utf-8", errors="replace"))


def _write_file(sb: SandboxSession, args: dict[str, Any]) -> str:
    sb.write_file(args["path"], args["content"])
    return json.dumps({"written": args["path"], "bytes": len(args["content"].encode())})


BUILTIN_TOOLS: dict[str, Tool] = {
    tool.name: tool
    for tool in [
        Tool(
            name="run_shell",
            description="Run a shell command inside the sandbox. Returns exit_code, stdout, stderr.",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to run."},
                    "working_directory": {"type": "string", "description": "Optional working directory."},
                },
                "required": ["command"],
            },
            run=_run_shell,
        ),
        Tool(
            name="read_file",
            description="Read a UTF-8 text file from the sandbox filesystem.",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
            run=_read_file,
        ),
        Tool(
            name="write_file",
            description="Create or overwrite a text file in the sandbox filesystem.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
            run=_write_file,
        ),
    ]
}


def select_tools(names: tuple[str, ...]) -> list[Tool]:
    missing = [n for n in names if n not in BUILTIN_TOOLS]
    if missing:
        raise KeyError(f"Unknown tool(s): {missing}. Known: {sorted(BUILTIN_TOOLS)}")
    return [BUILTIN_TOOLS[n] for n in names]
