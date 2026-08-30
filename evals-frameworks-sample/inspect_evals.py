"""
Inspect harness — Restaurant Reservation Agent
==============================================
The SAME eval as ../agent-evals-sample, expressed in Inspect (UK AI Security
Institute). Framework: https://github.com/UKGovernmentBEIS/inspect_ai

Concept mapping (four boxes -> Inspect):
  DATASET  -> [Sample(...)] built from cases.CASES
  RUNNER   -> a @solver that calls agent.handle_reservation (our shipped system)
  GRADER   -> a @scorer running deterministic + state, then delegating the
              open-ended part to the built-in model_graded_qa (LLM-as-judge)
  METRIC   -> accuracy() + stderr(), aggregated across epochs (= trials)

Why Inspect reads differently from DeepEval: the four boxes are EXPLICIT, named
arguments of Task(...). `epochs=k` is first-class — pass@k falls out of running
each sample k times. This is the "research-grade" shape.

Run:
  pip install -r requirements.txt
  inspect eval inspect_evals.py --model openai/gpt-4o --epochs 5
  inspect view          # local HTML viewer of every trial + transcript
Environment: set OPENAI_API_KEY (agent + judge).
"""

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.solver import solver, TaskState, Generate
from inspect_ai.scorer import scorer, Score, CORRECT, INCORRECT, accuracy, stderr
from inspect_ai.model import get_model

from agent import handle_reservation, Reservation
from cases import CASES, Case
from graders_core import deterministic_check, state_check

# id -> Case, so the scorer can recover the full ground-truth region per sample.
_BY_ID: dict[str, Case] = {c.id: c for c in CASES}


# ── DATASET ───────────────────────────────────────────────────────────────────
def _dataset() -> list[Sample]:
    return [
        Sample(
            id=c.id,
            input=c.request,
            target=", ".join(c.accepted_status),      # human-readable ground truth
            metadata={"case_id": c.id, "type": c.type},
        )
        for c in CASES
    ]


# ── RUNNER: wrap the shipped agent as a solver ───────────────────────────────
@solver
def reservation_solver():
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        output, meta = handle_reservation(state.input_text)
        # Stash the parsed object + a text completion for the scorer to read.
        state.metadata["reservation"] = output
        state.metadata["latency_ms"] = meta.get("latency_ms")
        completion = output.model_dump_json(indent=2) if output else "<AGENT ERROR>"
        state.output.completion = completion
        return state
    return solve


# ── GRADER: deterministic + state, then LLM-as-judge for the rubric ──────────
JUDGE_TEMPLATE = """You are grading a restaurant reservation agent.

Customer request:
{question}

Agent response:
{answer}

The response PASSES only if ALL of these hold:
{criterion}

First reason briefly, then end with exactly 'GRADE: C' (pass) or 'GRADE: I' (fail).
"""


@scorer(metrics=[accuracy(), stderr()])
def reservation_scorer():
    async def score(state: TaskState, target) -> Score:
        # Resolve the judge lazily: get_model() with no arg = the active eval
        # model. Pass get_model("openai/gpt-4o") to decouple judge from agent.
        judge = get_model()
        case = _BY_ID[state.metadata["case_id"]]
        output: Reservation | None = state.metadata.get("reservation")

        # Cheap rungs first — if they fail, no need to spend a judge call.
        det_ok, det_msg = deterministic_check(output, case)
        if not det_ok:
            return Score(value=INCORRECT, explanation=f"deterministic: {det_msg}")
        state_ok, state_msg = state_check(output, case)
        if not state_ok:
            return Score(value=INCORRECT, explanation=f"state: {state_msg}")

        if not case.rubric:
            return Score(value=CORRECT, explanation="cheap graders passed; no rubric")

        # Rung 4: LLM-as-judge for the open-ended criteria.
        criterion = "\n".join(f"- {r}" for r in case.rubric)
        prompt = JUDGE_TEMPLATE.format(
            question=case.request, answer=state.output.completion, criterion=criterion
        )
        result = await judge.generate(prompt)
        verdict = "GRADE: C" in result.completion.upper().replace("GRADE:C", "GRADE: C")
        return Score(
            value=CORRECT if verdict else INCORRECT,
            explanation=result.completion,
        )

    return score


# ── TASK: the four boxes, wired together. epochs=k => pass@k for free ─────────
@task
def restaurant_reservation():
    return Task(
        dataset=_dataset(),
        solver=reservation_solver(),
        scorer=reservation_scorer(),
        epochs=5,
    )
