# Evals, in real frameworks — the same eval, two ways

This is the companion to the hand-rolled harness in [`../agent-evals-sample`](../agent-evals-sample).
There, we built the four boxes of an eval **from scratch**. Here, we run the **exact
same eval** — same agent, same golden set — inside two real frameworks so you can
see what a library gives you for free.

> An LLM call is a **random variable**, not a function — so correctness is a
> **statistic**, not a property. Every file here is about measuring that statistic.

## The four boxes (and where they live)

| Box | What it is | Hand-rolled (`agent-evals-sample`) | This repo |
|-----|-----------|-------------------------------------|-----------|
| **Dataset** | cases + ground-truth *region* | `tasks.yaml` | [`cases.py`](cases.py) |
| **Runner** | the *shipped* system under test | `agent.py` | [`agent.py`](agent.py) (shared) |
| **Grader** | output → score (the oracle) | 3 graders in `run_evals.py` | [`graders_core.py`](graders_core.py) + each harness |
| **Metric** | aggregate → one number | `compute_pass_at_k()` | `accuracy()`/`stderr()` or the pass-rate print |

Ground truth is a **set of constraints**, not a golden string (that's why `==`
dies): `accepted_status ∈ {confirmed, waitlisted}`, keywords that must appear,
typed field checks, and natural-language rubric assertions for the judge.

## The grading ladder (cheapest rung that's still true)

Both harnesses run the ladder in order and only pay for the expensive rung when
the cheap ones pass:

1. **Deterministic / typed checks** — `party_size == 4`, status in the accepted set. Free, exact.
2. **State check** — required keywords present in the outcome text. Cheap.
3. **LLM-as-judge** — the open-ended rubric ("was the message warm?"). Costs a model call; carries bias.

## Capability vs regression

Cases are split by `type`. **Capability** = can it do the thing (book the table).
**Regression** = does it still refuse what it must refuse (decline Monday, decline
a party of 20). Report them separately — a capability gain must never hide a
safety regression inside one blended average.

## Run it

```bash
pip install -r requirements.txt
cp .env.template .env   # add OPENAI_API_KEY
```

### DeepEval (pytest-style — "an eval is a unit test you already know")
```bash
deepeval test run deepeval_evals.py             # cheap graders only
RUN_LLM_JUDGE=1 deepeval test run deepeval_evals.py   # + LLM rubric judge
```
Key teaching point in [`deepeval_evals.py`](deepeval_evals.py): we **do not
`assert` per trial**. A stochastic assert is a flaky test. We run `EPOCHS`
trials and **measure** pass-rate / pass@k / pass^k.

### Inspect (research-grade — the four boxes are explicit `Task(...)` args)
```bash
inspect eval inspect_evals.py --model openai/gpt-4o --epochs 5
inspect view    # HTML viewer: every trial, transcript, and score
```
Key teaching point in [`inspect_evals.py`](inspect_evals.py): `epochs=k` is
first-class, so **pass@k falls out for free**, and `Task(dataset=…, solver=…,
scorer=…)` names the boxes for you.

## DeepEval vs Inspect at a glance

| | DeepEval | Inspect |
|---|---|---|
| Mental model | pytest test file | `Task(dataset, solver, scorer)` |
| Trials / pass@k | `@parametrize` loop (manual) | `epochs=k` (native) |
| LLM judge | `GEval(criteria="plain English")` | `model_graded_qa` / custom scorer |
| Runner | implicit (called in the test) | explicit `@solver` |
| Best for | CI, onboarding, RAG/agent metrics | safety research, agent + sandbox evals |

## The wider landscape

| Category | Tools |
|----------|-------|
| **Offline eval libraries** | Inspect, DeepEval, OpenAI Evals, lm-eval-harness, HELM (maintenance), RAGAS, promptfoo |
| **Eval + observability platforms** (offline **and** online) | LangSmith, Langfuse, Arize Phoenix, Braintrust, W&B Weave |
| **Benchmarks** (real oracles) | SWE-bench Verified (run the repo's tests), τ-bench (final DB state), WebArena (page state), GAIA (exact match), AgentBench (per-env reward), LMArena (human Elo) |
| **Guardrails** | NeMo Guardrails, Guardrails AI, Llama Guard, OpenAI moderation |

Rule of thumb: **libraries** are your CI unit-tests (frozen golden set);
**platforms** are your production monitoring (trace → score live traffic);
**benchmarks** are the standardized exams you quote to compare models.

## Files

```
agent.py          # shared RUNNER (the system under test)
cases.py          # shared DATASET (golden set, ground-truth regions)
graders_core.py   # shared cheap GRADERS (deterministic + state)
deepeval_evals.py # DeepEval harness (pytest-style)
inspect_evals.py  # Inspect harness (Task/solver/scorer)
```
