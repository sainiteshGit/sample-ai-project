"""Live MAST demo: produce all three failure buckets with real model calls.

    .venv/bin/python mast_live_demo.py --repeats 5

~2 + repeats*2 billable calls. Uses the existing Azure/OpenAI .env config.
Coordination reuses the real fault_injection_demo code path (no
re-implementation). Specification and Capability are new live experiments:
we do not label anything by hand -- each verdict is derived from measured
model output across repeats.
"""

import argparse
import json

from pydantic import BaseModel, ConfigDict, ValidationError

from fault_injection_demo import REQUESTS, run_case
from live_eval_demo import make_client


# ---------------------------------------------------------------------------
# Specification: an instruction with a genuine, undefined gap. If the model's
# own answers disagree across repeats on the *same* input, that disagreement
# is real, measured evidence the instruction under-specifies the case --
# not something we asserted ourselves.
# ---------------------------------------------------------------------------

SPEC_PROMPT = """You triage support tickets. Escalate the ticket to the
on-call engineer if it is urgent. Reply only JSON: {"action": "escalate"
or "no_escalate"}."""

SPEC_TICKET = (
    "Customer says the app feels slow sometimes, no error messages, "
    "no crash, been happening on and off for a few weeks."
)


class SpecDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str


def run_spec_trial(client, model: str) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SPEC_PROMPT},
            {"role": "user", "content": SPEC_TICKET},
        ],
        response_format={"type": "json_object"},
        max_completion_tokens=256,
    )
    return SpecDecision.model_validate_json(response.choices[0].message.content).action


# ---------------------------------------------------------------------------
# Capability: instruction is unambiguous, data is clean and complete. If the
# model still gets the arithmetic wrong some fraction of the time, that is a
# measured reasoning error rate, not a handoff or spec problem.
# ---------------------------------------------------------------------------

CAP_PROMPT = """You approve or deny refunds. Policy: refund only if the
order was placed within the last 30 days of today. Order date and today's
date are both given exactly; do not ask for more information. Reply only
JSON: {"decision": "refund" or "deny"}."""

CAP_CASE = "Order date: 2024-01-05. Today's date: 2024-02-20."
CAP_EXPECTED = "deny"  # 46 days apart, outside the 30-day window


class CapDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str


def run_cap_trial(client, model: str) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": CAP_PROMPT},
            {"role": "user", "content": CAP_CASE},
        ],
        response_format={"type": "json_object"},
        max_completion_tokens=256,
    )
    return CapDecision.model_validate_json(response.choices[0].message.content).decision


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error("--repeats must be positive")

    try:
        client, model = make_client()
    except ValueError as exc:
        parser.error(str(exc))

    print(f"LIVE MAST DEMO | {model} | {args.repeats} repeats per live bucket\n")

    with client:
        # --- Specification ---------------------------------------------
        print("1) SPECIFICATION -- same ambiguous ticket, repeated live calls")
        spec_actions = []
        for i in range(args.repeats):
            try:
                action = run_spec_trial(client, model)
            except (ValidationError, json.JSONDecodeError) as exc:
                action = f"invalid_response({exc.__class__.__name__})"
            spec_actions.append(action)
            print(f"   trial {i + 1}: {action}")
        distinct = sorted(set(spec_actions))
        verdict_spec = (
            "Specification failure -- instruction is ambiguous"
            if len(distinct) > 1
            else "No disagreement observed this run -- inconclusive, not proof of a clear spec"
        )
        print(f"   distinct answers seen: {distinct}")
        print(f"   verdict: {verdict_spec}\n")

        # --- Coordination (reuses real fault_injection_demo code) ------
        print("2) COORDINATION -- reusing the real fault_injection_demo run")
        result = run_case(client, model, REQUESTS[1], "persistent-drop")
        handoffs = [e for e in result["trace"] if e["stage"] == "availability_handoff"]
        mismatch = any(e["source"]["available"] and e["delivered"] is None for e in handoffs)
        for e in handoffs:
            state = "OPEN" if e["source"]["available"] else "CLOSED"
            received = "MISSING" if e["injected_drop"] else state
            print(f"   lookup {e['lookup']}: tool={state} -> delivered={received}")
        print(f"   actions: {result['actions']} | safe={result['safe']} completed={result['completed']}")
        verdict_coord = (
            "Coordination failure -- tool was correct, model never received it"
            if mismatch else "No mismatch observed this run"
        )
        print(f"   verdict: {verdict_coord}\n")

        # --- Capability --------------------------------------------------
        print("3) CAPABILITY -- clear policy, clean data, repeated live calls")
        cap_decisions = []
        for i in range(args.repeats):
            try:
                decision = run_cap_trial(client, model)
            except (ValidationError, json.JSONDecodeError) as exc:
                decision = f"invalid_response({exc.__class__.__name__})"
            cap_decisions.append(decision)
            print(f"   trial {i + 1}: {decision}")
        errors = sum(1 for d in cap_decisions if d != CAP_EXPECTED)
        error_rate = errors / len(cap_decisions)
        verdict_cap = (
            f"Capability failure observed -- {errors}/{len(cap_decisions)} wrong "
            f"despite clear policy and clean data"
            if errors else "No reasoning error observed this run"
        )
        print(f"   expected: {CAP_EXPECTED} | measured error rate: {error_rate:.0%}")
        print(f"   verdict: {verdict_cap}\n")

    print("SUMMARY")
    print(f"{'Bucket':<16}{'Verdict'}")
    print(f"{'Specification':<16}{verdict_spec}")
    print(f"{'Coordination':<16}{verdict_coord}")
    print(f"{'Capability':<16}{verdict_cap}")
    print(
        "\nEach verdict above comes from measured live output this run, not a "
        "hand-labeled scenario. Re-run with a higher --repeats for a more "
        "stable read, especially for specification and capability."
    )


if __name__ == "__main__":
    main()
