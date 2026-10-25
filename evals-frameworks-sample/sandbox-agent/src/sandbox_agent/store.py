"""JSON-file store for agents created in the UI. Built-in agents live in agents.py."""

from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Any

from sandbox_agent.agent import AgentSpec
from sandbox_agent.tools import BUILTIN_TOOLS

_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{1,39}$")
MAX_STEPS_LIMIT = 30


class AgentStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or os.environ.get("SANDBOX_AGENT_STORE", "agents.json"))
        self._lock = threading.Lock()

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def list(self) -> list[AgentSpec]:
        with self._lock:
            return [_from_dict(d) for d in self._read().values()]

    def get(self, name: str) -> AgentSpec | None:
        with self._lock:
            data = self._read().get(name)
        return _from_dict(data) if data else None

    def save(self, spec: AgentSpec) -> AgentSpec:
        """Validate and insert or replace an agent spec."""
        _validate(spec)
        with self._lock:
            data = self._read()
            data[spec.name] = _to_dict(spec)
            self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return spec


def _validate(spec: AgentSpec) -> None:
    if not _NAME_RE.match(spec.name):
        raise ValueError("name must be 2-40 chars: lowercase letters, digits, '-' or '_'")
    if not spec.instructions.strip():
        raise ValueError("instructions must not be empty")
    unknown = set(spec.tools) - set(BUILTIN_TOOLS)
    if unknown:
        raise ValueError(f"unknown tools: {sorted(unknown)}; allowed: {sorted(BUILTIN_TOOLS)}")
    if not 1 <= spec.max_steps <= MAX_STEPS_LIMIT:
        raise ValueError(f"max_steps must be between 1 and {MAX_STEPS_LIMIT}")


def _to_dict(spec: AgentSpec) -> dict[str, Any]:
    return {
        "name": spec.name,
        "instructions": spec.instructions,
        "tools": list(spec.tools),
        "max_steps": spec.max_steps,
        "run_mode": spec.run_mode,
    }


def _from_dict(d: dict[str, Any]) -> AgentSpec:
    return AgentSpec(
        name=d["name"],
        instructions=d["instructions"],
        tools=tuple(d["tools"]),
        max_steps=int(d["max_steps"]),
        run_mode=d.get("run_mode", "auto"),
    )
