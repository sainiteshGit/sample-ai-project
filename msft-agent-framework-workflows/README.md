# Workflows Benchmark — Monolithic vs Sequential vs Concurrent (C#)

Side-by-side benchmark of three ways to handle the same multi-step task in
**Microsoft Agent Framework** using `AgentWorkflowBuilder`.

The task is a small **travel-reimbursement pipeline**:

1. **Parse** a free-form request into structured fields
2. **Apply policy** (caps, submission window) and decide a verdict
3. **Draft** a short employee-facing decision email

Three implementations of the same pipeline:

| Pattern | What it does | Calls |
|---|---|---|
| **Monolithic** | One agent, one prompt — all 3 jobs jammed together | 1 model turn |
| **Sequential** | 3 single-purpose agents wired with `BuildSequential` | 3 model turns |
| **Concurrent** | Parser first, then policy + drafter run in parallel via `BuildConcurrent` | 3 model turns (2 parallel) |

Three axes measured per run:

- **Cost** — input + output tokens summed across every model call (no free pass for orchestration)
- **Latency** — wall-clock ms from request to final output
- **Correctness** — substring match against policy-specific keywords (e.g. `APPROVE`, `$75`, `30 days`)

## Run

```bash
cp appsettings.Development.json.template appsettings.Development.json
# fill in your Azure OpenAI endpoint and (optionally) key
dotnet run
```

If `ApiKey` is empty, the project uses `DefaultAzureCredential`.

## What to look for

- **Monolithic** is cheapest in turns and usually fastest, but the model has to
  juggle three responsibilities in one context. Watch for cases where the verdict
  drifts because the email-drafting concern leaked into the policy decision.
- **Sequential** pays 3x the round trips. It's the slowest, but each agent stays
  in its lane — the policy agent sees only structured fields, never the raw user
  story.
- **Concurrent** parallelizes the last two steps. Same total token cost as
  Sequential, but lower wall-clock latency. Useful when the downstream steps
  don't depend on each other.

## Files

- [Agents.cs](Agents.cs) — three single-purpose agents + the monolithic version
- [Prompts.cs](Prompts.cs) — six test cases with policy-specific expected keywords
- [Program.cs](Program.cs) — benchmark runner, prints correctness / cost / latency tables
