"""The agent loop: model proposes tool calls, tools run in the sandbox, trace is recorded."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

ApproveFn = Callable[[str, str], bool]  # (tool name, raw JSON arguments) -> allowed?
EventFn = Callable[[dict[str, Any]], None]

from sandbox_agent.llm import ChatModel
from sandbox_agent.sandbox import SandboxProvider, SandboxSpec
from sandbox_agent.tools import Tool


@dataclass(frozen=True)
class AgentSpec:
    name: str
    instructions: str
    tools: tuple[str, ...] = ("run_shell", "read_file", "write_file")
    sandbox: SandboxSpec = field(default_factory=SandboxSpec)
    max_steps: int = 10
    # "auto": tools run as the model asks. "review": each tool call needs human approval first.
    run_mode: str = "auto"

    def __post_init__(self) -> None:
        if self.run_mode not in ("auto", "review"):
            raise ValueError(f"run_mode must be 'auto' or 'review', got {self.run_mode!r}")


@dataclass
class ToolCallRecord:
    step: int
    name: str
    arguments: str  # raw model output, kept verbatim for grading
    result: str | None
    error: str | None


@dataclass
class RunResult:
    agent: str
    task: str
    final_answer: str | None
    stop_reason: str  # "completed" | "max_steps"
    steps: int
    tool_calls: list[ToolCallRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Agent:
    def __init__(
        self,
        spec: AgentSpec,
        model: ChatModel,
        provider: SandboxProvider,
        tools: list[Tool],
    ):
        self.spec = spec
        self._model = model
        self._provider = provider
        self._tools = {t.name: t for t in tools}

    def run(
        self,
        task: str,
        attachments: dict[str, bytes] | None = None,
        approve: ApproveFn | None = None,
        on_event: EventFn | None = None,
    ) -> RunResult:
        """Run one task in a fresh sandbox.

        attachments maps sandbox paths to file bytes. In review mode, approve is required and
        is called before every tool call; a False answer skips the call and tells the model.
        on_event receives a dict for each step so a UI can stream the trace live.
        """
        if self.spec.run_mode == "review" and approve is None:
            raise ValueError("review mode needs an approve callback")
        emit: EventFn = on_event or (lambda _event: None)
        schemas = [t.schema() for t in self._tools.values()]
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.spec.instructions},
            {"role": "user", "content": task},
        ]
        result = RunResult(
            agent=self.spec.name, task=task, final_answer=None, stop_reason="max_steps", steps=0
        )

        with self._provider.session(self.spec.sandbox) as sandbox:
            emit({"type": "sandbox_started"})
            for path, data in (attachments or {}).items():
                sandbox.write_file(path, data.decode("utf-8"))
            for step in range(1, self.spec.max_steps + 1):
                result.steps = step
                reply = self._model.complete(messages, schemas)

                if not reply.tool_calls:
                    result.final_answer = reply.content
                    result.stop_reason = "completed"
                    emit({"type": "final", "answer": reply.content})
                    return result

                messages.append(
                    {
                        "role": "assistant",
                        "content": reply.content,
                        "tool_calls": [
                            {
                                "id": c.id,
                                "type": "function",
                                "function": {"name": c.name, "arguments": c.arguments},
                            }
                            for c in reply.tool_calls
                        ],
                    }
                )
                for call in reply.tool_calls:
                    emit({"type": "tool_proposed", "step": step, "name": call.name,
                          "arguments": call.arguments})
                    if approve is not None and not approve(call.name, call.arguments):
                        output, error = None, "denied: the user rejected this tool call; choose another approach or finish"
                    else:
                        output, error = self._execute(sandbox, call.name, call.arguments)
                    record = ToolCallRecord(
                        step=step,
                        name=call.name,
                        arguments=call.arguments,
                        result=output,
                        error=error,
                    )
                    result.tool_calls.append(record)
                    emit({"type": "tool_result", **asdict(record)})
                    # Errors go back to the model so it can recover; the trace keeps them for grading.
                    payload = output if error is None else json.dumps({"error": error})
                    messages.append({"role": "tool", "tool_call_id": call.id, "content": payload})

        return result

    def _execute(self, sandbox: Any, name: str, raw_args: str) -> tuple[str | None, str | None]:
        tool = self._tools.get(name)
        if tool is None:
            return None, f"unknown tool: {name}"
        try:
            args = json.loads(raw_args or "{}")
        except json.JSONDecodeError as exc:
            return None, f"invalid JSON arguments: {exc}"
        if not isinstance(args, dict):
            return None, "arguments must be a JSON object"
        try:
            return tool.run(sandbox, args), None
        except KeyError as exc:
            return None, f"missing argument: {exc}"
        except Exception as exc:  # tool failures are data, not crashes
            return None, f"{type(exc).__name__}: {exc}"
