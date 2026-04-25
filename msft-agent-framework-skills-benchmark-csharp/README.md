# Skills vs. Inlined Instructions — C# Token Benchmark

Empirically measures the token cost of two agent designs that solve the **same** Contoso operations tasks, using **Microsoft Agent Framework** (`Microsoft.Agents.AI` 1.0.0-rc4) on Azure OpenAI.

| Agent | Pattern | What sits in the system prompt every turn |
|---|---|---|
| **BaselineAgent** | All `SKILL.md` files concatenated into `Instructions` | Full bodies of every skill (~thousands of tokens) |
| **SkillsAgent**   | `FileAgentSkillsProvider` (progressive disclosure) | Only short skill descriptions (~100 tokens each) |

Both agents are pointed at the **same** 5-skill folder:

```
skills/
├── code-style/SKILL.md
├── data-privacy/SKILL.md
├── expense-policy/SKILL.md
├── refund-policy/SKILL.md
└── unit-converter/SKILL.md
```

## Setup

```bash
cp appsettings.Development.json.template appsettings.Development.json
# edit Endpoint + ApiKey + DeploymentName
dotnet run
```

If `ApiKey` is left blank the program falls back to `DefaultAzureCredential`.

## What it does

1. Builds both agents.
2. Runs each prompt from [`Prompts.cs`](Prompts.cs) against **both** agents in a fresh session (so the baseline always pays the full system-prompt cost — apples-to-apples).
3. Reads `response.RawRepresentation` (the underlying `ChatResponse.Usage`) to capture real `InputTokenCount` / `OutputTokenCount` / `TotalTokenCount` reported by the model.
4. Prints a per-prompt and aggregate comparison table.

Example output shape:

```
prompt                  baseline-in    skills-in      saved    saved %
----------------------------------------------------------------------
expense_simple                3,812          840      2,972      78.0%
refund_used_item              3,812          720      3,092      81.1%
code_review_python            3,812          690      3,122      81.9%
privacy_deletion              3,812          810      3,002      78.8%
unit_conversion               3,812          560      3,252      85.3%
control_no_skill              3,812          410      3,402      89.2%
multi_skill                   3,812        1,180      2,632      69.0%
----------------------------------------------------------------------
TOTAL                        26,684        5,210     21,474      80.5%
```

(Numbers will vary slightly by model and tokenizer.)

## Why the savings exist

- **Baseline**: every turn re-sends the entire concatenated `SKILL.md` corpus, regardless of whether the question needs it.
- **Skills**: only the skill *descriptions* are advertised. The agent decides which skill is relevant, calls `load_skill` to fetch just that body, and ignores the rest.

## Caveats

- The skills agent can add a **tool-call round trip** the first time it loads a skill in a session, which raises *output* tokens slightly. The win is in *input* tokens, which scale with conversation length and dominate cost in real workloads.
- For very small skill catalogs (1–2 skills, < 500 tokens), inlining can be cheaper.
- Scripts / resources inside skills are not exercised by this benchmark — adding them would tilt the comparison further toward skills (deterministic compute = zero LLM tokens).

## References

- Skills docs: <https://learn.microsoft.com/en-us/agent-framework/agents/skills?pivots=programming-language-csharp>
- Open spec: <https://agentskills.io/>
