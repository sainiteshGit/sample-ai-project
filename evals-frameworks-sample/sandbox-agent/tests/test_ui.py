"""Offline tests for review mode, the agent store, sessions, and the web API. No Azure needed."""

from __future__ import annotations

import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

from sandbox_agent.agent import Agent, AgentSpec
from sandbox_agent.llm import ModelReply
from sandbox_agent.sessions import SessionManager
from sandbox_agent.store import AgentStore
from sandbox_agent.tools import select_tools
from sandbox_agent.web import create_app

from test_agent import FakeProvider, ScriptedModel, call


def review_agent(replies):
    provider = FakeProvider()
    spec = AgentSpec(name="r", instructions="be terse", max_steps=5, run_mode="review")
    agent = Agent(spec, ScriptedModel(replies), provider, select_tools(spec.tools))
    return agent, provider


def test_review_mode_requires_approve_callback():
    agent, _ = review_agent([ModelReply(content="x")])
    with pytest.raises(ValueError):
        agent.run("hi")


def test_denied_tool_call_is_not_executed_and_error_goes_to_trace():
    replies = [call("run_shell", json.dumps({"command": "rm -rf /"})), ModelReply(content="ok")]
    agent, provider = review_agent(replies)
    seen = []

    result = agent.run("clean up", approve=lambda name, args: False, on_event=seen.append)

    assert provider.sandbox.commands == []
    assert "denied" in result.tool_calls[0].error
    assert [e["type"] for e in seen if e["type"] == "tool_proposed"] == ["tool_proposed"]


def test_approved_tool_call_runs():
    replies = [call("run_shell", json.dumps({"command": "echo ok"})), ModelReply(content="done")]
    agent, provider = review_agent(replies)

    result = agent.run("say ok", approve=lambda name, args: True)

    assert provider.sandbox.commands == ["echo ok"]
    assert result.tool_calls[0].error is None


def test_store_round_trip_and_validation(tmp_path):
    store = AgentStore(tmp_path / "agents.json")
    spec = AgentSpec(name="log-triager", instructions="triage logs", tools=("run_shell",))
    store.save(spec)

    reloaded = AgentStore(tmp_path / "agents.json")
    assert reloaded.get("log-triager").instructions == "triage logs"
    assert [s.name for s in reloaded.list()] == ["log-triager"]

    with pytest.raises(ValueError):
        store.save(AgentSpec(name="Bad Name!", instructions="x"))
    with pytest.raises(ValueError):
        store.save(AgentSpec(name="empty", instructions="   "))
    with pytest.raises(ValueError):
        store.save(AgentSpec(name="badtool", instructions="x", tools=("nope",)))


def _wait_for(predicate, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_session_review_flow_waits_for_decision():
    provider = FakeProvider()

    def factory(spec):
        return Agent(spec, ScriptedModel([call("run_shell", json.dumps({"command": "echo hi"})), ModelReply(content="done")]), provider, select_tools(spec.tools))

    manager = SessionManager(factory)
    spec = AgentSpec(name="r", instructions="x", run_mode="review")
    session = manager.start(spec, "say hi")

    assert _wait_for(lambda: session.status == "waiting_approval")
    pending_id = session.pending["id"]
    manager.decide(session.id, pending_id, True)

    assert _wait_for(lambda: session.status == "completed")
    assert provider.sandbox.commands == ["echo hi"]


def test_session_records_error_status():
    def factory(spec):
        raise RuntimeError("boom")

    manager = SessionManager(factory)
    session = manager.start(AgentSpec(name="e", instructions="x"), "task")
    assert _wait_for(lambda: session.status == "error")
    assert "boom" in session.error


@pytest.fixture()
def client(tmp_path):
    provider = FakeProvider()

    def factory(spec):
        return Agent(spec, ScriptedModel([ModelReply(content="hello")]), provider, select_tools(spec.tools))

    app = create_app(manager=SessionManager(factory), store=AgentStore(tmp_path / "agents.json"))
    return TestClient(app)


def test_api_create_agent_and_run_session(client):
    assert client.get("/api/tools").status_code == 200
    created = client.post(
        "/api/agents",
        json={"name": "helper", "instructions": "be helpful", "tools": ["run_shell"], "max_steps": 3, "run_mode": "auto"},
    )
    assert created.status_code == 201

    names = [a["name"] for a in client.get("/api/agents").json()]
    assert "helper" in names

    run = client.post("/api/agents/helper/sessions", json={"task": "say hello"})
    assert run.status_code == 201
    sid = run.json()["id"]

    def finished():
        return client.get(f"/api/sessions/{sid}").json()["status"] == "completed"

    assert _wait_for(finished)
    body = client.get(f"/api/sessions/{sid}").json()
    assert body["result"]["final_answer"] == "hello"


def test_api_rejects_builtin_name_and_bad_input(client):
    assert client.post("/api/agents", json={"name": "csv_analyst", "instructions": "x"}).status_code == 409
    assert client.post("/api/agents", json={"name": "ok-name", "instructions": "  "}).status_code == 400
    assert client.post("/api/agents/missing/sessions", json={"task": "x"}).status_code == 404
    assert client.get("/api/sessions/nope").status_code == 404
