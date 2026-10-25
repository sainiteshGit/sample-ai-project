"""Runs agent sessions in background threads and lets a UI stream events and answer approvals.

One session = one task = one sandbox (created by the agent's run and deleted when it ends).
In review mode the worker thread blocks on each tool call until decide() is called.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sandbox_agent.agent import Agent, AgentSpec

AgentFactory = Callable[[AgentSpec], Agent]


@dataclass
class Session:
    id: str
    agent: str
    task: str
    status: str = "running"  # running | waiting_approval | completed | max_steps | error
    events: list[dict[str, Any]] = field(default_factory=list)
    pending: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    _decision: threading.Event = field(default_factory=threading.Event, repr=False)
    _allowed: bool = field(default=False, repr=False)

    def view(self, since: int = 0) -> dict[str, Any]:
        return {
            "id": self.id,
            "agent": self.agent,
            "task": self.task,
            "status": self.status,
            "pending": self.pending,
            "error": self.error,
            "result": self.result,
            "events": self.events[since:],
            "next_seq": len(self.events),
        }


class SessionManager:
    def __init__(self, factory: AgentFactory):
        self._factory = factory
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def start(
        self,
        spec: AgentSpec,
        task: str,
        attachments: dict[str, bytes] | None = None,
    ) -> Session:
        if not task.strip():
            raise ValueError("task must not be empty")
        session = Session(id=uuid.uuid4().hex[:12], agent=spec.name, task=task)
        with self._lock:
            self._sessions[session.id] = session
        threading.Thread(
            target=self._run,
            args=(session, spec, attachments),
            name=f"session-{session.id}",
            daemon=True,
        ).start()
        return session

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            return self._sessions.get(session_id)

    def list(self) -> list[Session]:
        with self._lock:
            return list(self._sessions.values())

    def decide(self, session_id: str, pending_id: str, allow: bool) -> None:
        session = self._require(session_id)
        with self._lock:
            if session.pending is None or session.pending["id"] != pending_id:
                raise ValueError("no matching pending approval (it may have already been answered)")
            session._allowed = allow
        session._decision.set()

    def _require(self, session_id: str) -> Session:
        session = self.get(session_id)
        if session is None:
            raise KeyError(session_id)
        return session

    def _run(self, session: Session, spec: AgentSpec, attachments: dict[str, bytes] | None) -> None:
        def on_event(event: dict[str, Any]) -> None:
            with self._lock:
                session.events.append(event)

        def approve(name: str, arguments: str) -> bool:
            with self._lock:
                session.pending = {"id": uuid.uuid4().hex[:8], "name": name, "arguments": arguments}
                session.status = "waiting_approval"
                session._decision.clear()
            session._decision.wait()
            with self._lock:
                allowed = session._allowed
                session.pending = None
                session.status = "running"
            return allowed

        try:
            agent = self._factory(spec)
            result = agent.run(
                session.task,
                attachments=attachments,
                approve=approve if spec.run_mode == "review" else None,
                on_event=on_event,
            )
            with self._lock:
                session.result = result.to_dict()
                session.status = result.stop_reason
        except Exception as exc:  # surface any failure to the UI instead of dying silently
            with self._lock:
                session.error = f"{type(exc).__name__}: {exc}"
                session.status = "error"
