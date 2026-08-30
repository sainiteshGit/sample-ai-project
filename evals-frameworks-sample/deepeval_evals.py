"""
DeepEval harness — Restaurant Reservation Agent
===============================================
The SAME eval as ../agent-evals-sample, expressed in DeepEval (Confident AI).
Framework: https://github.com/confident-ai/deepeval

Concept mapping (four boxes -> DeepEval):
  DATASET  -> cases.CASES turned into LLMTestCase objects
  RUNNER   -> agent.handle_reservation (called inside the pytest test)
  GRADER   -> a BaseMetric subclass (deterministic + state) + GEval (LLM judge)
  METRIC   -> pass rate over EPOCHS trials, printed at the end

Why pytest? DeepEval's whole pitch is "evals look like unit tests you already
know." The catch (see below): a plain assert makes a stochastic system a flaky
test. So we DON'T assert per-trial — we run k epochs and MEASURE the rate.

Run:
  pip install -r requirements.txt
  # exact-match / state graders only (no judge, no API cost for grading):
  deepeval test run deepeval_evals.py
  # with the LLM-as-judge rubric metric:
  RUN_LLM_JUDGE=1 deepeval test run deepeval_evals.py
Environment: set OPENAI_API_KEY (used by BOTH the agent and GEval's judge).
"""

import os
import collections

import pytest
from deepeval.test_case import LLMTestCase, SingleTurnParams
from deepeval.metrics import GEval, BaseMetric

from agent import handle_reservation, Reservation
from cases import CASES, Case
from graders_core import deterministic_check, state_check

EPOCHS = int(os.getenv("EPOCHS", "5"))          # trials per case (Lab 10)
RUN_LLM_JUDGE = os.getenv("RUN_LLM_JUDGE") == "1"

# Aggregate pass counts across trials so we can print pass-rate / pass@k / pass^k.
_RESULTS: dict[str, list[bool]] = collections.defaultdict(list)


# ── GRADER 1+2: deterministic + state, as one DeepEval custom metric ──────────
class ReservationRulesMetric(BaseMetric):
    """Wraps the cheap, trustworthy rungs (typed checks + keyword state check)."""

    def __init__(self, case: Case, threshold: float = 1.0):
        self.threshold = threshold
        self.case = case
        self.evaluation_model = "rule-based"

    def measure(self, test_case: LLMTestCase) -> float:
        output: Reservation | None = test_case.additional_metadata.get("reservation")
        det_ok, det_msg = deterministic_check(output, self.case)
        state_ok, state_msg = state_check(output, self.case)
        self.success = det_ok and state_ok
        self.score = 1.0 if self.success else 0.0
        self.reason = f"deterministic: {det_msg}; state: {state_msg}"
        return self.score

    async def a_measure(self, test_case: LLMTestCase) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success

    @property
    def __name__(self):
        return "ReservationRules"


def _rubric_metric(case: Case) -> GEval:
    """GRADER 3: LLM-as-judge. Criteria are plain English -> that IS the prompt."""
    criteria = (
        "Evaluate the agent's reservation response against ALL of these, and only "
        "pass if every one holds:\n- " + "\n- ".join(case.rubric)
    )
    return GEval(
        name="ReservationRubric",
        criteria=criteria,
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        threshold=0.7,
    )


# ── DATASET x EPOCHS: pytest parametrization gives us the trials ──────────────
_PARAMS = [(case, trial) for case in CASES for trial in range(EPOCHS)]


@pytest.mark.parametrize("case,trial", _PARAMS, ids=[f"{c.id}#{t}" for c, t in _PARAMS])
def test_reservation(case: Case, trial: int):
    # RUNNER: call the shipped system
    output, _meta = handle_reservation(case.request)
    actual = output.model_dump_json(indent=2) if output else "<AGENT ERROR>"

    test_case = LLMTestCase(
        input=case.request,
        actual_output=actual,
        additional_metadata={"reservation": output},
    )

    metrics: list[BaseMetric] = [ReservationRulesMetric(case)]
    if RUN_LLM_JUDGE and case.rubric:
        metrics.append(_rubric_metric(case))

    # Measure each metric WITHOUT asserting (a stochastic assert = a flaky test).
    passed = True
    for m in metrics:
        m.measure(test_case)
        passed = passed and m.is_successful()
    _RESULTS[case.id].append(passed)


def teardown_module(_module):
    """METRIC: turn per-trial booleans into pass-rate / pass@k / pass^k."""
    print("\n\n=== Reservation eval — measured over EPOCHS trials ===")
    print(f"{'case':<26}{'type':<12}{'pass-rate':>10}{'pass@k':>9}{'pass^k':>9}")
    for case in CASES:
        trials = _RESULTS.get(case.id, [])
        k = len(trials)
        if not k:
            continue
        p = sum(trials) / k
        print(f"{case.id:<26}{case.type:<12}{p:>9.0%}{1-(1-p)**k:>9.0%}{p**k:>9.0%}")
