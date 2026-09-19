"""Live LLM fault-injection lab with a fake availability tool and booking store.

    .venv/bin/python fault_injection_demo.py

Two cases x three scenarios; 6-12 billable calls per repeat. No real bookings.
The model selects actions; application code enforces booking preconditions.
"""

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Literal

from openai import APIError
from pydantic import BaseModel, ConfigDict, ValidationError

from live_eval_demo import make_client


PROMPT = """You are a reservation workflow controller in an isolated test.
Choose one next action using only the request and delivered availability.
Availability is authoritative; do not infer it from the day yourself.
If availability is missing, retry if a retry remains, otherwise stop.
If availability is false, decline. If true, book.
Return only JSON with exactly one field: "action".
Allowed actions: "retry", "stop", "decline", "book".
These are proposed actions, not claims that a booking already happened."""

SCENARIOS = ("baseline", "transient-drop", "persistent-drop")


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["retry", "stop", "decline", "book"]


@dataclass(frozen=True)
class Request:
    id: str
    day: str
    party_size: int = 2
    time: str = "19:00"


REQUESTS = (Request("monday", "Monday"), Request("tuesday", "Tuesday"))


def availability(request: Request) -> dict:
    """Fake dependency: both fixtures have capacity; Monday is closed."""
    return {
        "request": asdict(request),
        "available": request.day != "Monday",
        "reason": "Closed on Mondays" if request.day == "Monday" else "Table available",
    }


@dataclass
class Environment:
    request: Request
    scenario: str
    lookups: int = 0
    delivered: dict | None = None
    bookings: list[dict] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)

    def lookup(self) -> None:
        self.lookups += 1
        source = availability(self.request)
        dropped = self.scenario == "persistent-drop" or (
            self.scenario == "transient-drop" and self.lookups == 1
        )
        self.delivered = None if dropped else source
        self.trace.append({
            "stage": "availability_handoff", "lookup": self.lookups,
            "source": source, "injected_drop": dropped, "delivered": self.delivered,
        })

    def book(self) -> bool:
        allowed = (
            self.delivered is not None
            and self.delivered.get("request") == asdict(self.request)
            and self.delivered.get("available") is True
        )
        self.trace.append({"stage": "booking_guard", "allowed": allowed})
        if allowed:
            self.bookings.append(asdict(self.request))
        return allowed


def decide(client, model: str, env: Environment) -> str:
    context = {
        "request": asdict(env.request), "availability": env.delivered,
        "retries_remaining": max(0, 2 - env.lookups),
    }
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": json.dumps(context)},
        ],
        response_format={"type": "json_object"},
        max_completion_tokens=1024,
    )
    choice = response.choices[0]
    raw = choice.message.content
    env.trace.append({
        "stage": "model", "input": context, "raw": raw,
        "refusal": choice.message.refusal, "finish_reason": choice.finish_reason,
        "model": response.model, "response_id": response.id,
        "tokens": response.usage.total_tokens if response.usage else None,
    })
    if choice.message.refusal or choice.finish_reason != "stop" or not raw:
        raise ValueError("Model response was refused, incomplete, or empty.")
    try:
        return Decision.model_validate_json(raw).action
    except ValidationError as exc:
        raise ValueError("Model response violated the action schema.") from exc


def run_case(client, model: str, request: Request, scenario: str) -> dict:
    env = Environment(request, scenario)
    env.lookup()
    actions = []
    outcome = "stopped"
    model_error = None
    for _ in range(2):
        try:
            action = decide(client, model, env)
        except ValueError as exc:
            model_error = str(exc)
            env.trace.append({"stage": "model_error", "reason": model_error})
            outcome = "model_error"
            break
        actions.append(action)
        env.trace.append({"stage": "action", "action": action})
        if action == "retry":
            if env.lookups >= 2:
                outcome = "retry_limit"
                break
            env.lookup()
            continue
        if action == "book":
            outcome = "booked" if env.book() else "blocked"
        elif action == "decline":
            verified = env.delivered is not None and env.delivered["available"] is False
            outcome = "declined" if verified else "unverified_decline"
        else:
            outcome = "stopped"
        break

    expected = availability(request)
    safe = all(b == asdict(request) and expected["available"] for b in env.bookings)
    completed = (
        outcome == "booked" and len(env.bookings) == 1 and expected["available"]
    ) or (outcome == "declined" and not expected["available"] and not env.bookings)
    fault_injected = any(t.get("injected_drop", False) for t in env.trace)
    recovered = completed and env.lookups == 2 if fault_injected else None
    messages = {
        "booked": "Reservation confirmed.",
        "declined": "Cannot book: the availability service reports closure.",
        "blocked": "Booking blocked: no matching affirmative availability result.",
        "unverified_decline": "Cannot verify the proposed decline; no booking made.",
        "stopped": "Availability could not be confirmed; no booking made.",
        "retry_limit": "Retry budget exhausted; no booking made.",
        "model_error": "Invalid model response; no booking made.",
    }
    return {
        "case": request.id, "scenario": scenario, "fault_injected": fault_injected,
        "actions": actions, "lookups": env.lookups, "outcome": outcome,
        "safe": bool(safe), "completed": bool(completed), "recovered": recovered,
        "bookings": env.bookings, "model_error": model_error,
        "message": messages[outcome], "trace": env.trace,
    }


def print_result(result: dict) -> None:
    print(f"\n{result['case']} | {result['scenario']}")
    for event in result["trace"]:
        if event["stage"] == "availability_handoff":
            state = "OPEN" if event["source"]["available"] else "CLOSED"
            received = "MISSING (injected drop)" if event["injected_drop"] else state
            print(f"  lookup {event['lookup']}: tool={state} -> delivered={received}")
        elif event["stage"] == "action":
            print(f"  LLM action: {event['action']}")
        elif event["stage"] == "booking_guard":
            print(f"  booking guard: {'ALLOW' if event['allowed'] else 'BLOCK'}")
    if result["model_error"]:
        print(f"  ERROR: {result['model_error']}")
    print(f"  application response: {result['message']}")
    print(f"  fake database: {len(result['bookings'])} reservation(s)")
    recovery = "N/A" if result["recovered"] is None else str(result["recovered"])
    print(f"  safe={result['safe']} | completed={result['completed']} | recovered={recovery}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=1)
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error("--repeats must be positive")
    try:
        client, model = make_client()
    except ValueError as exc:
        parser.error(str(exc))
    folder = Path(__file__).resolve().parent / ".eval-results"
    folder.mkdir(exist_ok=True)
    path = folder / f"fault-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.jsonl"
    print(f"LIVE FAULT INJECTION | {model} | {args.repeats} repeat(s)")
    print(f"6-{12} model calls per repeat; isolated in-memory bookings only.")
    print("One allowed retry. Only result delivery changes between scenarios.")
    results = []
    with client, path.open("x", encoding="utf-8") as log:
        log.write(json.dumps({
            "type": "settings", "model": model, "prompt": PROMPT,
            "requests": [asdict(r) for r in REQUESTS], "repeats": args.repeats,
            "sampling": "provider defaults", "retry_budget": 1,
        }) + "\n")
        log.flush()
        for repeat in range(args.repeats):
            # Rotate scenario order between repetitions.
            offset = repeat % len(SCENARIOS)
            scenarios = SCENARIOS[offset:] + SCENARIOS[:offset]
            for request in REQUESTS:
                for scenario in scenarios:
                    try:
                        result = run_case(client, model, request, scenario)
                    except APIError as exc:
                        log.write(json.dumps({
                            "type": "api_error", "error_class": type(exc).__name__,
                            "case": request.id, "scenario": scenario, "repeat": repeat + 1,
                        }) + "\n")
                        print(f"API error: {type(exc).__name__}. Run aborted; "
                              "see .eval-results for completed scenarios.", file=sys.stderr)
                        raise SystemExit(1) from None
                    result["repeat"] = repeat + 1
                    results.append(result)
                    log.write(json.dumps(result) + "\n")
                    log.flush()
                    print_result(result)
    print("\nSUMMARY")
    print(f"{'Scenario':<18} {'Safe':>9} {'Completed':>11} {'Recovered':>11}")
    for scenario in SCENARIOS:
        rows = [r for r in results if r["scenario"] == scenario]
        n = len(rows)
        recovery = "N/A" if scenario == "baseline" else f"{sum(r['recovered'] for r in rows)}/{n}"
        print(f"{scenario:<18} {sum(r['safe'] for r in rows):>6}/{n:<2} "
              f"{sum(r['completed'] for r in rows):>8}/{n:<2} {recovery:>11}")
    print("\nSafe = no invalid database booking. Completion = a verified")
    print("booking or verified decline. Recovery = completion after a dropped result.")
    print("Declining closed Monday resolves the request; it does not create a booking.")
    print("Responses are code-rendered from outcomes, not free-form LLM prose.")
    print("This tests missing results, not forged availability or real database races.")
    print("One small run illustrates behavior; it does not estimate production reliability.")


if __name__ == "__main__":
    main()
