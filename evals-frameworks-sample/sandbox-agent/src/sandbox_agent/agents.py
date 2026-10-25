"""Named agent specs. Add a new agent here; the CLI and code can refer to it by name."""

from sandbox_agent.agent import AgentSpec
from sandbox_agent.store import AgentStore

AGENTS: dict[str, AgentSpec] = {
    "default": AgentSpec(
        name="default",
        instructions=(
            "You are a software agent running inside an isolated Linux sandbox. "
            "Use the tools to carry out the user's instruction. Prefer verifying results "
            "with a command before answering. When the task is done, reply with a short "
            "plain-text summary and do not call any more tools."
        ),
    ),
    "csv_analyst": AgentSpec(
        name="csv_analyst",
        instructions=(
            "You analyze a tabular data file that has been uploaded to /workspace/data.csv "
            "inside your sandbox. Write a short Python script to /workspace/analyze.py using "
            "write_file, run it with `python3 /workspace/analyze.py` using run_shell, and read "
            "the output. Base every number in your answer on that output; if the script fails, "
            "fix it and rerun. Answer the user's question in plain text with the figures you "
            "computed. Do not call tools after you have the answer."
        ),
        tools=("run_shell", "read_file", "write_file"),
        max_steps=12,
    ),
}


def get_agent_spec(name: str, store: AgentStore | None = None) -> AgentSpec:
    """Resolve a built-in agent first, then a user-created one from the store."""
    if name in AGENTS:
        return AGENTS[name]
    spec = (store or AgentStore()).get(name)
    if spec is None:
        known = sorted(set(AGENTS) | {s.name for s in (store or AgentStore()).list()})
        raise KeyError(f"Unknown agent {name!r}. Known: {known}")
    return spec


def list_agent_specs(store: AgentStore | None = None) -> list[AgentSpec]:
    return list(AGENTS.values()) + (store or AgentStore()).list()

