"""Offline tests: fake sandbox and scripted model. No Azure needed."""

from __future__ import annotations

import json
from contextlib import contextmanager

import pytest

from sandbox_agent.agent import Agent, AgentSpec
from sandbox_agent.llm import ModelReply, ToolCallRequest
from sandbox_agent.sandbox import SandboxSpec
from sandbox_agent.tools import select_tools


class FakeExecResult:
    def __init__(self, exit_code=0, stdout="", stderr=""):
        self.exit_code, self.stdout, self.stderr = exit_code, stdout, stderr


class FakeSandbox:
    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.commands: list[str] = []

    def exec(self, command, working_directory=None):
        self.commands.append(command)
        return FakeExecResult(stdout=f"ran: {command}")

    def read_file(self, path):
        return self.files[path]

    def write_file(self, path, content):
        self.files[path] = content.encode()


class FakeProvider:
    def __init__(self):
        self.sandbox = FakeSandbox()
        self.created = 0
        self.deleted = 0

    @contextmanager
    def session(self, spec: SandboxSpec):
        self.created += 1
        try:
            yield self.sandbox
        finally:
            self.deleted += 1


class ScriptedModel:
    """Returns pre-written replies in order, and records what it was shown."""

    def __init__(self, replies):
        self._replies = list(replies)
        self.seen_tool_names: list[list[str]] = []

    def complete(self, messages, tools):
        self.seen_tool_names.append([t["function"]["name"] for t in tools])
        return self._replies.pop(0)


def call(name, arguments, call_id="c1"):
    return ModelReply(content=None, tool_calls=[ToolCallRequest(call_id, name, arguments)])


def make_agent(replies, max_steps=5):
    provider = FakeProvider()
    model = ScriptedModel(replies)
    spec = AgentSpec(name="t", instructions="be terse", max_steps=max_steps)
    agent = Agent(spec, model, provider, select_tools(spec.tools))
    return agent, provider, model


def test_completes_after_tool_call_and_records_trace():
    agent, provider, _ = make_agent(
        [
            call("run_shell", json.dumps({"command": "echo hi"})),
            ModelReply(content="done"),
        ]
    )
    result = agent.run("say hi")

    assert result.stop_reason == "completed"
    assert result.final_answer == "done"
    assert result.steps == 2
    assert provider.sandbox.commands == ["echo hi"]
    record = result.tool_calls[0]
    assert (record.step, record.name, record.error) == (1, "run_shell", None)
    assert '"stdout": "ran: echo hi"' in record.result


def test_sandbox_is_created_and_deleted_once_per_run():
    agent, provider, _ = make_agent([ModelReply(content="ok")])
    agent.run("noop")
    assert (provider.created, provider.deleted) == (1, 1)


def test_sandbox_is_deleted_even_when_model_raises():
    class Boom:
        def complete(self, messages, tools):
            raise RuntimeError("model down")

    provider = FakeProvider()
    spec = AgentSpec(name="t", instructions="x")
    agent = Agent(spec, Boom(), provider, select_tools(spec.tools))
    with pytest.raises(RuntimeError):
        agent.run("anything")
    assert provider.deleted == 1


def test_invalid_json_arguments_are_reported_not_raised():
    agent, provider, _ = make_agent([call("run_shell", "{not json"), ModelReply(content="gave up")])
    result = agent.run("x")
    assert result.tool_calls[0].error.startswith("invalid JSON arguments")
    assert provider.sandbox.commands == []
    assert result.stop_reason == "completed"


def test_unknown_tool_is_reported_and_not_executed():
    agent, _, _ = make_agent([call("delete_everything", "{}"), ModelReply(content="ok")])
    result = agent.run("x")
    assert result.tool_calls[0].error == "unknown tool: delete_everything"


def test_missing_argument_is_reported():
    agent, provider, _ = make_agent([call("write_file", json.dumps({"path": "a"})), ModelReply(content="ok")])
    result = agent.run("x")
    assert result.tool_calls[0].error.startswith("missing argument")
    assert provider.sandbox.files == {}


def test_stops_at_max_steps():
    replies = [call("run_shell", json.dumps({"command": "true"}), f"c{i}") for i in range(3)]
    agent, _, _ = make_agent(replies, max_steps=3)
    result = agent.run("loop forever")
    assert result.stop_reason == "max_steps"
    assert result.steps == 3
    assert result.final_answer is None


def test_model_sees_only_selected_tools():
    provider = FakeProvider()
    model = ScriptedModel([ModelReply(content="ok")])
    spec = AgentSpec(name="t", instructions="x", tools=("read_file",))
    Agent(spec, model, provider, select_tools(spec.tools)).run("x")
    assert model.seen_tool_names == [["read_file"]]


def test_trace_serialises_to_json():
    agent, _, _ = make_agent([call("run_shell", json.dumps({"command": "ls"})), ModelReply(content="ok")])
    payload = json.dumps(agent.run("x").to_dict())
    assert json.loads(payload)["tool_calls"][0]["name"] == "run_shell"


def test_attachments_are_written_to_sandbox_before_first_step():
    agent, provider, _ = make_agent([ModelReply(content="ok")])
    agent.run("x", attachments={"/workspace/data.csv": b"a,b\n1,2\n"})
    assert provider.sandbox.files == {"/workspace/data.csv": b"a,b\n1,2\n"}


def test_select_tools_rejects_unknown_names():
    with pytest.raises(KeyError):
        select_tools(("run_shell", "nope"))
