# sandbox-agent

A small, reusable Python harness: define an agent, give it tools, and every
instruction it executes runs inside an Azure Container Apps sandbox. Each run
gets its own sandbox, which is deleted when the run ends.

```
task ──► Agent loop ──► ChatModel (Azure OpenAI)      proposes tool calls
              │
              └──► Tool ──► SandboxSession (Azure sandbox)   executes them
              │
              └──► RunResult (full trace: every call, args, output, error)
```

## Layout

| Path | Role |
|---|---|
| `src/sandbox_agent/sandbox.py` | Sandbox lifecycle (create, yield, delete in `finally`) |
| `src/sandbox_agent/tools.py` | Tool definitions (`run_shell`, `read_file`, `write_file`) |
| `src/sandbox_agent/llm.py` | `ChatModel` protocol and Azure OpenAI adapter |
| `src/sandbox_agent/agent.py` | Agent loop and trace (`AgentSpec`, `RunResult`) |
| `src/sandbox_agent/agents.py` | Named agent registry. Add new agents here. |
| `src/sandbox_agent/cli.py` | `sandbox-agent "task" [--agent NAME] [--json]` |
| `tests/` | Offline tests with a fake sandbox and scripted model |

## Setup

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env   # then fill in the values
```

Azure prerequisites:
- A sandbox group (created with `SandboxGroupManagementClient.create_group`, or the Azure portal).
- Your identity needs the **Container Apps SandboxGroup Data Owner** role at subscription or resource-group scope.
- The sandbox service is in preview and uses Entra ID auth only.

## Run

```bash
.venv/bin/python -m pytest                      # offline, no Azure needed
.venv/bin/sandbox-agent "echo hello from the sandbox"
.venv/bin/sandbox-agent --json "list files in /tmp"
```

## Web UI

```bash
.venv/bin/sandbox-agent-ui     # then open http://127.0.0.1:8000
```

- Create an agent: name, instructions, tools, max steps, and run mode. Agents are saved to `agents.json` (gitignored; override with `SANDBOX_AGENT_STORE`).
- Open an agent and run a task. Each run gets its own sandbox, which is deleted when the run ends. The live trace shows every tool call and result.
- **Auto** mode runs tools without asking. **Review** mode pauses before each tool call and waits for Allow or Deny. A denied call is never executed, and the denial goes back to the model as an error.

Design model: this follows the Azure SRE Agent pattern of extension points plus a governance gate on every proposed tool call. Review mode is the human-in-the-loop version of that gate.

Limits: sessions live in memory, so they are lost on restart. There is no cancel button, and a review-mode run waits indefinitely for a decision.

## Design notes

- **One sandbox per run.** Created at the start, deleted in `finally`, so cleanup happens even if the model raises.
- **Tool errors are data.** Bad JSON, unknown tools, and missing arguments go back to the model as `{"error": ...}` and are recorded in the trace. The loop continues.
- **The trace is the eval input.** `RunResult.to_dict()` gives JSON that a grader can score later: which tools ran, with what arguments, and whether the sandbox state matches the goal.
- **`max_steps` bounds the loop.** Hitting it sets `stop_reason="max_steps"`.
