"""Measure real LLM reservation responses using deterministic grading.

    .venv/bin/python live_eval_demo.py --repeats 5

Four cases, two prompt versions, five repeats = 40 billable model calls.
Uses the existing Azure/OpenAI .env configuration. No LLM judge is called.
Raw responses and experiment settings are saved locally in .eval-results/.
"""

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
import time

from openai import APIError, AzureOpenAI, OpenAI
from pydantic import ValidationError

from agent import Reservation, SYSTEM_PROMPT
from cases import Case
from graders_core import deterministic_check
from simple_geval_demo import _config


CASES = [
    Case(
        id="weekday",
        type="capability",
        request="Reserve an indoor table for 2 on Tuesday at 6 PM.",
        accepted_status=["confirmed"],
        checks=[{"field": "party_size", "equals": 2}],
    ),
    Case(
        id="monday",
        type="regression",
        request="Reserve an indoor table for 2 on Monday at 7 PM.",
        accepted_status=["declined"],
        checks=[{"field": "party_size", "equals": 2}],
    ),
    Case(
        id="peak",
        type="capability",
        request="Reserve an indoor table for 6 on Friday at 8 PM.",
        accepted_status=["waitlisted"],
        checks=[{"field": "party_size", "equals": 6}],
    ),
    Case(
        id="capacity",
        type="regression",
        request="Reserve an indoor table for 20 on Tuesday at 6 PM.",
        accepted_status=["declined"],
        checks=[{"field": "party_size", "equals": 20}],
    ),
]

PROMPTS = {
    "A": SYSTEM_PROMPT,
    "B": SYSTEM_PROMPT + (
        "\nBefore answering, check the requested day, party size, and time. "
        "Apply closure and capacity limits before the peak-hour rule. "
        "Keep party_size equal to the requested count even when declining. "
        "Return declined for Monday or a party above 12, waitlisted for "
        "an otherwise eligible Friday/Saturday peak request, and confirmed "
        "for other eligible requests."
    ),
}


@dataclass
class Result:
    repeat: int
    case_id: str
    version: str
    passed: bool
    reason: str
    raw: str | None
    refusal: str | None
    finish_reason: str
    model: str
    fingerprint: str | None
    latency_ms: float
    tokens: int | None
    request_id: str


def wilson_interval(passes: int, n: int) -> tuple[float, float]:
    """95% Wilson interval for independent Bernoulli trials."""
    if n <= 0 or not 0 <= passes <= n:
        raise ValueError("Require n > 0 and 0 <= passes <= n.")
    rate = passes / n
    z = 1.959963984540054
    denominator = 1 + z * z / n
    center = (rate + z * z / (2 * n)) / denominator
    half = z * math.sqrt(rate * (1 - rate) / n + z * z / (4 * n * n))
    half /= denominator
    return max(0.0, center - half), min(1.0, center + half)


def grade(raw: str | None, case: Case) -> tuple[bool, str]:
    if not raw:
        return False, "No answer text."
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return False, "Answer is not valid JSON."
    if not isinstance(payload, dict):
        return False, "Answer is not a JSON object."
    try:
        reservation = Reservation.model_validate(payload)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(map(str, error['loc']))}: {error['msg']}"
            for error in exc.errors(include_input=False, include_url=False)
        )
        return False, f"Reservation schema: {details}"
    return deterministic_check(reservation, case)


def make_client():
    endpoint, key, model = _config()
    if not key:
        raise ValueError("Set AZURE_OPENAI_API_KEY or OPENAI_API_KEY in .env.")
    if endpoint and not endpoint.endswith("/openai/v1"):
        # Root Azure endpoints use the versioned API; v1 endpoints use OpenAI.
        if ".openai.azure.com" in endpoint or ".services.ai.azure.com" in endpoint:
            return AzureOpenAI(
                azure_endpoint=endpoint, api_key=key,
                api_version="2024-10-21", timeout=90, max_retries=0,
            ), model
    return OpenAI(
        api_key=key, base_url=endpoint or None, timeout=90, max_retries=0,
    ), model


def evaluate(client, model: str, case: Case, version: str, repeat: int) -> Result:
    start = time.perf_counter()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": PROMPTS[version]},
            {"role": "user", "content": case.request},
        ],
        response_format={"type": "json_object"},
        max_completion_tokens=2048,
    )
    choice = response.choices[0]
    raw = choice.message.content
    passed, reason = grade(raw, case)
    if choice.message.refusal:
        passed, reason = False, "Model refused the request."
    elif choice.finish_reason != "stop":
        passed, reason = False, f"Incomplete response: {choice.finish_reason}."
    return Result(
        repeat=repeat, case_id=case.id, version=version, passed=passed,
        reason=reason, raw=raw, refusal=choice.message.refusal,
        finish_reason=choice.finish_reason, model=response.model,
        fingerprint=response.system_fingerprint,
        latency_ms=(time.perf_counter() - start) * 1000,
        tokens=response.usage.total_tokens if response.usage else None,
        request_id=response.id,
    )


def report(results: list[Result], cases: list[Case], repeats: int) -> None:
    print("\nPER-CASE RESULTS (95% Wilson intervals)")
    print(f"{'Case':<10} {'Version':<8} {'Passes':>7} {'Rate':>7}  Interval")
    for case in cases:
        for version in PROMPTS:
            rows = [r for r in results if r.case_id == case.id and r.version == version]
            passes = sum(r.passed for r in rows)
            low, high = wilson_interval(passes, len(rows))
            print(f"{case.id:<10} {version:<8} {passes:>3}/{len(rows):<3} "
                  f"{passes / len(rows):6.1%}  {low:.1%} to {high:.1%}")

    print("\nFIXED-SUITE SUMMARY (equal weight per case)")
    rates = {}
    for version in PROMPTS:
        rows = [r for r in results if r.version == version]
        passes = sum(r.passed for r in rows)
        rates[version] = passes / len(rows)
        print(f"{version}: {passes}/{len(rows)} = {rates[version]:.1%}")
    print(f"B minus A: {(rates['B'] - rates['A']) * 100:+.1f} percentage points")
    paired = {(r.repeat, r.case_id, r.version): r.passed for r in results}
    fixes = regressions = 0
    for repeat in range(1, repeats + 1):
        for case in cases:
            a = paired[repeat, case.id, "A"]
            b = paired[repeat, case.id, "B"]
            fixes += not a and b
            regressions += a and not b
    print(f"Paired attempts: {fixes} A-fail/B-pass; {regressions} A-pass/B-fail")
    print("Pairs match case and repeat, not model randomness.")
    print("These are observed differences, not established improvements.")
    print("\nIntervals assume independent repeats with stable conditions.")
    print("They describe these cases, not unseen requests or overall quality.")
    print("Passing checks schema, status, and party size, not tone or all fields.")
    if all(r.passed for r in results):
        print("All attempts passed. This run shows no measured gain for B.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--case", choices=["all"] + [c.id for c in CASES], default="all")
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error("--repeats must be positive")
    cases = [c for c in CASES if args.case in ("all", c.id)]
    try:
        client, model = make_client()
    except ValueError as exc:
        parser.error(str(exc))
    folder = Path(__file__).resolve().parent / ".eval-results"
    folder.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = folder / f"live-{stamp}.jsonl"
    metadata = {
        "type": "settings", "created_at": stamp, "model": model,
        "prompts": PROMPTS, "cases": [asdict(c) for c in cases],
        "repeats": args.repeats, "sampling": "provider defaults; no seed",
        "max_completion_tokens": 2048, "max_retries": 0,
        "order": "alternate A/B order by case and repeat",
        "grader": "Reservation schema + status + party_size",
    }
    print(f"LIVE LLM EVAL | deployment: {model}")
    print(f"{len(cases)} cases x {args.repeats} repeats x 2 versions "
          f"= {len(cases) * args.repeats * 2} billable calls")
    print("A: existing restaurant prompt. B: explicit rule-checking instruction.")
    print("Provider sampling defaults; no artificial failures or retries.", flush=True)
    results = []
    with client, path.open("x", encoding="utf-8") as log:
        log.write(json.dumps(metadata) + "\n")
        log.flush()
        for repeat in range(1, args.repeats + 1):
            for index, case in enumerate(cases):
                versions = ("A", "B") if (repeat + index) % 2 else ("B", "A")
                for version in versions:
                    try:
                        result = evaluate(client, model, case, version, repeat)
                    except APIError as exc:
                        log.write(json.dumps({
                            "type": "api_error", "error_class": type(exc).__name__,
                            "repeat": repeat, "case": case.id, "version": version,
                        }) + "\n")
                        print(f"\nAPI call failed: {type(exc).__name__}. "
                              f"Partial results saved at {path}.", file=sys.stderr)
                        raise SystemExit(1) from None
                    results.append(result)
                    log.write(json.dumps(asdict(result)) + "\n")
                    log.flush()
                    verdict = "PASS" if result.passed else "FAIL"
                    print(f"Repeat {repeat:2} | {case.id:<8} | {version} | {verdict}",
                          flush=True)
                    if not result.passed:
                        print(f"  {result.reason}", flush=True)
    report(results, cases, args.repeats)


if __name__ == "__main__":
    main()
