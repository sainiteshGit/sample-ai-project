"""Local web UI: create agents, run sandbox sessions from an agent, approve tool calls.

Start with:  sandbox-agent-ui   (then open http://127.0.0.1:8000)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from sandbox_agent.agent import Agent, AgentSpec
from sandbox_agent.agents import AGENTS, get_agent_spec, list_agent_specs
from sandbox_agent.llm import azure_openai_chat_model_from_env
from sandbox_agent.sandbox import AzureSandboxProvider, SandboxSettings
from sandbox_agent.sessions import AgentFactory, Session, SessionManager
from sandbox_agent.store import AgentStore
from sandbox_agent.tools import BUILTIN_TOOLS, select_tools

STATIC_DIR = Path(__file__).parent / "static"


def default_agent_factory(spec: AgentSpec) -> Agent:
    """Same wiring as the CLI: model + sandbox provider + tools -> Agent."""
    return Agent(
        spec=spec,
        model=azure_openai_chat_model_from_env(),
        provider=AzureSandboxProvider(SandboxSettings.from_env()),
        tools=select_tools(spec.tools),
    )


class AgentIn(BaseModel):
    name: str
    instructions: str
    tools: list[str] = Field(default_factory=lambda: ["run_shell", "read_file", "write_file"])
    max_steps: int = 10
    run_mode: str = "auto"


class SessionIn(BaseModel):
    task: str
    file_text: str | None = None  # optional contents saved to /workspace/data.csv


class DecisionIn(BaseModel):
    pending_id: str
    allow: bool


def _session_summary(s: Session) -> dict[str, Any]:
    return {"id": s.id, "agent": s.agent, "task": s.task, "status": s.status}


def _agent_dict(spec: AgentSpec) -> dict[str, Any]:
    return {
        "name": spec.name,
        "instructions": spec.instructions,
        "tools": list(spec.tools),
        "max_steps": spec.max_steps,
        "run_mode": spec.run_mode,
        "builtin": spec.name in AGENTS,
    }


def create_app(
    manager: SessionManager | None = None,
    store: AgentStore | None = None,
) -> FastAPI:
    store = store or AgentStore()
    manager = manager or SessionManager(default_agent_factory)
    app = FastAPI(title="sandbox-agent")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/api/tools")
    def tools() -> list[dict[str, str]]:
        return [{"name": t.name, "description": t.description} for t in BUILTIN_TOOLS.values()]

    @app.get("/api/agents")
    def list_agents() -> list[dict[str, Any]]:
        return [_agent_dict(s) for s in list_agent_specs(store)]

    @app.post("/api/agents", status_code=201)
    def create_agent(body: AgentIn) -> dict[str, Any]:
        if body.name in AGENTS:
            raise HTTPException(409, f"{body.name!r} is a built-in agent name")
        try:
            spec = AgentSpec(
                name=body.name,
                instructions=body.instructions,
                tools=tuple(body.tools),
                max_steps=body.max_steps,
                run_mode=body.run_mode,
            )
            store.save(spec)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        return _agent_dict(spec)

    @app.post("/api/agents/{name}/sessions", status_code=201)
    def start_session(name: str, body: SessionIn) -> dict[str, Any]:
        try:
            spec = get_agent_spec(name, store)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from None
        attachments = None
        if body.file_text is not None:
            attachments = {"/workspace/data.csv": body.file_text.encode("utf-8")}
        try:
            session = manager.start(spec, body.task, attachments=attachments)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        return _session_summary(session)

    @app.get("/api/sessions")
    def list_sessions(agent: str | None = None) -> list[dict[str, Any]]:
        sessions = manager.list()
        if agent:
            sessions = [s for s in sessions if s.agent == agent]
        return [_session_summary(s) for s in reversed(sessions)]

    @app.get("/api/sessions/{session_id}")
    def get_session(session_id: str, since: int = 0) -> dict[str, Any]:
        session = manager.get(session_id)
        if session is None:
            raise HTTPException(404, "unknown session")
        return session.view(since=since)

    @app.post("/api/sessions/{session_id}/decisions")
    def decide(session_id: str, body: DecisionIn) -> dict[str, str]:
        try:
            manager.decide(session_id, body.pending_id, body.allow)
        except KeyError:
            raise HTTPException(404, "unknown session") from None
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None
        return {"status": "allowed" if body.allow else "denied"}

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("sandbox_agent.web:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
