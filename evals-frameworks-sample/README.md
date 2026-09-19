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

## Offline demo: trusting an eval score

[`trust_eval_demo.py`](trust_eval_demo.py) needs only Python 3.9 or newer.
No packages, API key, or model calls are required. From this directory:

```bash
python3 trust_eval_demo.py
```

The four examples cover sampling variation, Wilson confidence intervals,
simulated version comparisons, and equal averages hiding different failures.
Outputs explicitly distinguish simulations from constructed example counts;
they are not measured LLM performance.

For separate screenshots or a different random draw:

```bash
python3 trust_eval_demo.py --demo variation
python3 trust_eval_demo.py --demo confidence
python3 trust_eval_demo.py --demo compare
python3 trust_eval_demo.py --demo distribution
python3 trust_eval_demo.py --seed 7
```

The confidence intervals assume independent trials with a fixed success
probability. Real evals spanning different cases need an analysis appropriate
to that sampling design. A simulated version winning more often is not itself
a statistical significance test.

## Live LLM demo: measuring prompt reliability

[`live_eval_demo.py`](live_eval_demo.py) calls the configured Azure/OpenAI model
on four fixed reservation requests using two prompt versions. It reuses the
reservation schema, deterministic grader, environment configuration, and Wilson
interval helper from the other scripts in this directory. Use the existing
requirements and configure `.env` as for the judge demos.

```bash
.venv/bin/python live_eval_demo.py --repeats 5
```

This makes **40 billable model calls**. Each call creates a fresh conversation.
Version A uses the existing restaurant prompt; B adds explicit rule-checking
instructions. The grader checks schema validity, status, and party size, not
tone or every reservation field. No LLM judge or artificial failures are used.
The runner uses provider sampling defaults and alternates version order.
API errors abort the experiment rather than becoming semantic failures.

The final tables show per-case pass rates and Wilson intervals, then the
fixed-suite averages and paired attempt outcomes. Intervals assume independent
repeats under stable conditions. No pooled interval or significance claim is
made across heterogeneous cases. An all-pass run is valid evidence; it does
not establish perfection or an improvement from the new prompt.

For more repetitions of just the Monday case (40 calls):

```bash
.venv/bin/python live_eval_demo.py --case monday --repeats 20
```

Responses, prompts, grader outcomes, timing, model identifiers, and usage are
saved in gitignored `.eval-results/live-<timestamp>.jsonl` files. Treat these
files as local experiment artifacts, not production traffic logs.

## Live fault-injection lab

[`fault_injection_demo.py`](fault_injection_demo.py) uses the existing `.env`
and client configuration. A real model chooses workflow actions; the availability
tool and booking database are local fakes. No real reservations are created.

```bash
.venv/bin/python fault_injection_demo.py
```

The Monday (closed) and Tuesday (open) fixtures each run in three scenarios:
normal delivery, a first-result drop, and persistent result drops. Only the
handoff changes. Each scenario gets a fresh environment and at most one retry.
The default run costs 6-12 model calls. Use `--repeats 3` for 18-36 calls.
Scenario order rotates between repetitions.

The trace shows source availability, what the model actually received, proposed
actions, booking guard decisions, and the final in-memory database. Results are
saved to gitignored `.eval-results/`. API errors abort with an explicit error;
invalid model outputs are reported as incomplete scenarios.

Safety means no invalid database booking, completion means a verified booking
or verified decline, and recovery means completion after an injected drop.
Stopping safely is not completion. Customer messages are rendered by application
code, so this is not a test of free-form misleading LLM claims. The guard checks
an affirmative tool result bound to the exact request. It is not a defense
against corrupted tool contents, changing availability, or database races.

Deterministic regression checks (no API calls):

```bash
.venv/bin/python -m unittest test_fault_injection_demo.py
```

## Run the framework examples

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
