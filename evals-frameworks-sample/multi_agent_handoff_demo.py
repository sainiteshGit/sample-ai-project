"""Evaluate a real two-agent incident-routing workflow.

    .venv/bin/python multi_agent_handoff_demo.py --repeats 3

The intake and routing agents make real model calls. The on-call directory and
incident assignments are local, in-memory SQLite fixtures; nobody is paged.
The swap-service scenario deliberately changes the handoff after intake.
"""

import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys
from typing import Literal
from uuid import uuid4

from openai import APIError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from live_eval_demo import make_client

MAX_ROUTER_TURNS = 6
MAX_ROUTER_TOOL_CALLS = 12
SCENARIOS = ("baseline", "swap-service")

REQUEST = (
    "Incident INC-4821: payments-api is returning elevated 5xx errors. "
    "Severity is SEV2. Assign the incident to the on-call team for this service."
)
EXPECTED_HANDOFF = {
    "incident_id": "INC-4821",
    "service": "payments-api",
    "severity": "SEV2",
}
EXPECTED_ASSIGNMENT = {**EXPECTED_HANDOFF, "team": "payments-oncall"}
ROSTER = {
    "payments-api": "payments-oncall",
    "catalog-api": "catalog-oncall",
}
FIELDS = ("incident_id", "service", "severity")

INTAKE_PROMPT = (
    "You are the incident intake agent. Extract the incident ID, service, and "
    "severity from the request. Return only a JSON object with exactly "
    'three string fields: "incident_id", "service", and "severity". '
    "Preserve the values in the request; do not invent missing details."
)
ROUTER_PROMPT = (
    "You are the incident routing agent. The JSON you receive is the task "
    "handoff. Look up the on-call owner for its service. After a successful "
    "lookup, assign exactly the supplied incident ID, service, and severity "
    "to the team returned by that lookup. Call assign_incident at most once. "
    "Do not guess the team or claim an assignment succeeded without tool "
    "confirmation. If a necessary tool fails, stop and explain the failure."
)


class StrictObject(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Handoff(StrictObject):
    incident_id: str = Field(min_length=1)
    service: str = Field(min_length=1)
    severity: Literal["SEV1", "SEV2", "SEV3"]


class LookupArgs(StrictObject):
    service: str = Field(min_length=1)


class AssignmentArgs(Handoff):
    team: str = Field(min_length=1)


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_oncall_owner",
            "description": "Look up the on-call team responsible for a service.",
            "parameters": {
                "type": "object",
                "properties": {"service": {"type": "string"}},
                "required": ["service"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "assign_incident",
            "description": "Record an incident assignment in the local test database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "incident_id": {"type": "string"},
                    "service": {"type": "string"},
                    "severity": {"type": "string", "enum": ["SEV1", "SEV2", "SEV3"]},
                    "team": {"type": "string"},
                },
                "required": ["incident_id", "service", "severity", "team"],
                "additionalProperties": False,
            },
        },
    },
]


def new_database():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE owners (service TEXT PRIMARY KEY, team TEXT NOT NULL)")
    db.execute(
        "CREATE TABLE assignments ("
        "incident_id TEXT PRIMARY KEY, service TEXT NOT NULL, "
        "severity TEXT NOT NULL, team TEXT NOT NULL)"
    )
    db.executemany("INSERT INTO owners (service, team) VALUES (?, ?)", ROSTER.items())
    db.commit()
    return db


def lookup_oncall_owner(db, service):
    row = db.execute("SELECT team FROM owners WHERE service = ?", (service,)).fetchone()
    if row is None:
        return {"error": f"no on-call owner for service {service!r}"}
    return {"service": service, "team": row["team"]}


def assign_incident(db, incident_id, service, severity, team):
    owner = lookup_oncall_owner(db, service)
    if "error" in owner:
        return owner
    if owner["team"] != team:
        return {"error": "team does not own the supplied service"}
    if db.execute(
        "SELECT 1 FROM assignments WHERE incident_id = ?", (incident_id,)
    ).fetchone():
        return {"error": "incident already has an assignment"}
    # This fixture has no authoritative incident-to-service record. That is
    # the intentional gap the handoff experiment exposes.
    db.execute(
        "INSERT INTO assignments (incident_id, service, severity, team) VALUES (?, ?, ?, ?)",
        (incident_id, service, severity, team),
    )
    db.commit()
    return {"ok": True, "incident_id": incident_id, "team": team}


TOOLS = {
    "lookup_oncall_owner": (LookupArgs, lookup_oncall_owner),
    "assign_incident": (AssignmentArgs, assign_incident),
}


def validation_message(exc):
    return "; ".join(
        f"{'.'.join(map(str, error['loc'])) or 'JSON'}: {error['msg']}"
        for error in exc.errors(include_input=False, include_url=False)
    )


def execute_tool(db, name, raw_args):
    if name not in TOOLS:
        return {}, {"error": f"unknown tool: {name}"}
    schema, function = TOOLS[name]
    try:
        args = schema.model_validate_json(raw_args).model_dump()
    except ValidationError as exc:
        return {}, {"error": f"invalid tool arguments: {validation_message(exc)}"}
    return args, function(db, **args)


def run_intake(client, model):
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": INTAKE_PROMPT},
            {"role": "user", "content": REQUEST},
        ],
        response_format={"type": "json_object"},
        max_completion_tokens=1024,
    )
    if not response.choices:
        raise ValueError("Intake model returned no choices.")
    choice = response.choices[0]
    message = choice.message
    result = {
        "handoff": None,
        "raw": message.content,
        "error": None,
        "response": response.model_dump(mode="json", exclude_none=True),
    }
    if message.refusal:
        result["error"] = "Intake agent refused the request."
    elif choice.finish_reason != "stop":
        result["error"] = f"Intake response incomplete: {choice.finish_reason}."
    elif not message.content:
        result["error"] = "Intake agent returned no handoff."
    else:
        try:
            result["handoff"] = Handoff.model_validate_json(message.content).model_dump()
        except ValidationError as exc:
            result["error"] = f"Invalid intake handoff: {validation_message(exc)}"
    return result


def deliver_handoff(outgoing, scenario):
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario: {scenario}")
    incoming = dict(outgoing)
    if scenario == "swap-service":
        incoming["service"] = (
            "catalog-api" if outgoing["service"] != "catalog-api" else "payments-api"
        )
    return incoming


def run_router(client, model, incoming, db):
    messages = [
        {"role": "system", "content": ROUTER_PROMPT},
        {"role": "user", "content": json.dumps(incoming)},
    ]
    trace, responses = [], []

    def finish(completed, reason, final=""):
        return {
            "trace": trace,
            "responses": responses,
            "completed": completed,
            "stop_reason": reason,
            "final": final,
        }

    for turn in range(1, MAX_ROUTER_TURNS + 1):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOL_SCHEMAS,
            max_completion_tokens=1024,
        )
        responses.append(response.model_dump(mode="json", exclude_none=True))
        if not response.choices:
            raise ValueError("Routing model returned no choices.")
        choice = response.choices[0]
        message = choice.message
        if message.refusal:
            return finish(False, "routing agent refused the request")
        if not message.tool_calls:
            completed = (
                choice.finish_reason == "stop"
                and isinstance(message.content, str)
                and bool(message.content.strip())
            )
            return finish(completed, str(choice.finish_reason), message.content or "")
        if choice.finish_reason != "tool_calls":
            return finish(False, f"incomplete tool-call response: {choice.finish_reason}")
        messages.append(message.model_dump(exclude_none=True))
        for call in message.tool_calls:
            if len(trace) >= MAX_ROUTER_TOOL_CALLS:
                return finish(False, "tool-call budget exhausted")
            args, observation = execute_tool(db, call.function.name, call.function.arguments)
            trace.append({
                "turn": turn,
                "tool": call.function.name,
                "args": args,
                "raw_args": call.function.arguments,
                "observation": observation,
            })
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(observation),
            })
    return finish(False, "model-turn budget exhausted")


def check_fields(actual, expected):
    return [
        f"{field}: expected {expected[field]!r}, got {actual.get(field)!r}"
        for field in FIELDS
        if actual.get(field) != expected[field]
    ]


def verdict(errors):
    return {"status": "FAIL" if errors else "PASS", "reasons": errors}


def grade_router(router, incoming):
    errors = []
    if not router["completed"]:
        errors.append(f"routing agent did not complete: {router['stop_reason']}")
    lookups = []
    assignment_attempts = 0
    for event in router["trace"]:
        tool, args, observation = event["tool"], event["args"], event["observation"]
        if tool == "assign_incident":
            assignment_attempts += 1
        if "error" in observation:
            errors.append(f"{tool}: {observation['error']}")
            continue
        if tool == "lookup_oncall_owner":
            lookups.append((args["service"], observation["team"], event["turn"]))
        elif tool == "assign_incident":
            errors.extend(check_fields(args, incoming))
            if not any(
                service == args["service"]
                and team == args["team"]
                and lookup_turn < event["turn"]
                for service, team, lookup_turn in lookups
            ):
                errors.append("assignment did not follow an observed lookup for that service and team")
            if observation.get("ok") is not True:
                errors.append("assignment was not confirmed by the tool")
    if assignment_attempts != 1:
        errors.append(f"expected exactly one assignment attempt, got {assignment_attempts}")
    return verdict(errors)


def grade_run(intake, incoming, router, assignments):
    outgoing = intake["handoff"]
    if outgoing is None:
        intake_grade = verdict([intake["error"] or "No valid intake handoff."])
        skipped = {
            "status": "NOT RUN",
            "reasons": ["Intake did not produce a valid handoff."],
        }
        handoff_preserved = handoff_correct = router_grade = skipped
    else:
        intake_grade = verdict(check_fields(outgoing, EXPECTED_HANDOFF))
        handoff_preserved = verdict(check_fields(incoming, outgoing))
        handoff_correct = verdict(check_fields(incoming, EXPECTED_HANDOFF))
        router_grade = grade_router(router, incoming)
    outcome_errors = []
    if assignments != [EXPECTED_ASSIGNMENT]:
        outcome_errors.append("expected exactly one assignment to payments-oncall for INC-4821")
    return {
        "intake": intake_grade,
        "handoff_preserved": handoff_preserved,
        "handoff_correct": handoff_correct,
        "router": router_grade,
        "outcome": verdict(outcome_errors),
    }


def run_scenario(client, model, scenario, intake, repeat):
    with closing(new_database()) as db:
        outgoing = intake["handoff"]
        incoming = deliver_handoff(outgoing, scenario) if outgoing is not None else None
        router = run_router(client, model, incoming, db) if incoming is not None else None
        assignments = [
            dict(row)
            for row in db.execute(
                "SELECT incident_id, service, severity, team FROM assignments ORDER BY incident_id"
            )
        ]
    return {
        "scenario": scenario,
        "repeat": repeat,
        "configured_model": model,
        "request": REQUEST,
        "intake_prompt": INTAKE_PROMPT,
        "router_prompt": ROUTER_PROMPT,
        "expected_handoff": EXPECTED_HANDOFF,
        "expected_assignment": EXPECTED_ASSIGNMENT,
        "intake": intake,
        "incoming": incoming,
        "router": router,
        "assignments": assignments,
        "grades": grade_run(intake, incoming, router, assignments),
    }


GRADE_LABELS = (
    ("intake", "Intake"),
    ("handoff_preserved", "Handoff preserved"),
    ("handoff_correct", "Handoff correct"),
    ("router", "Router, given its input"),
    ("outcome", "Outcome"),
)


def print_result(result):
    print(f"\n{result['scenario']} | run {result['repeat']}")
    print(f"  Intake output: {json.dumps(result['intake']['handoff'])}")
    if result["intake"]["error"]:
        print(f"  Intake error: {result['intake']['error']}")
        print(f"  Raw intake output: {result['intake']['raw']!r}")
    print(f"  Delivered handoff: {json.dumps(result['incoming'])}")
    router = result["router"]
    if router is not None:
        for event in router["trace"]:
            print(
                f"  Turn {event['turn']}: {event['tool']}({json.dumps(event['args'])})"
                f" -> {json.dumps(event['observation'])}"
            )
        print(f"  Router completed: {router['completed']} ({router['stop_reason']})")
        print(f"  Router response (not graded): {json.dumps(router['final'])}")
    else:
        print("  Router not run: no valid intake handoff.")
    print(f"  Local assignments: {json.dumps(result['assignments'])}")
    for key, label in GRADE_LABELS:
        grade = result["grades"][key]
        print(f"  {label}: {grade['status']}")
        for reason in grade["reasons"]:
            print(f"    - {reason}")


def print_summary(results, scenarios):
    print("\nObserved results (small samples are not reliability estimates):")
    for scenario in scenarios:
        group = [result for result in results if result["scenario"] == scenario]
        print(f"  {scenario}:")
        for key, label in GRADE_LABELS:
            statuses = [result["grades"][key]["status"] for result in group]
            attempted = sum(status != "NOT RUN" for status in statuses)
            not_run = len(statuses) - attempted
            suffix = f"; {not_run} not run" if not_run else ""
            print(f"    {label}: {statuses.count('PASS')}/{attempted}{suffix}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--scenario", choices=("both", *SCENARIOS), default="both")
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error("--repeats must be positive")

    scenarios = list(SCENARIOS) if args.scenario == "both" else [args.scenario]
    client, model = make_client()
    directory = Path(__file__).resolve().parent / ".eval-results"
    directory.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = directory / f"multi-agent-handoff-{stamp}-{uuid4().hex[:8]}.jsonl"
    results = []
    print("Two real LLM agents; local SQLite directory and assignments. No one is paged.")
    print("swap-service deliberately changes the handoff; it is not a spontaneous failure.")
    print("Each repeat shares one intake output across scenarios; routing calls are independent.")
    print(f"Model/deployment: {model}")
    print(f"Request: {REQUEST}")
    print("Results:")
    try:
        with client, path.open("x", encoding="utf-8") as output:
            for repeat in range(1, args.repeats + 1):
                intake = run_intake(client, model)
                ordered = scenarios if repeat % 2 else list(reversed(scenarios))
                for scenario in ordered:
                    result = run_scenario(client, model, scenario, intake, repeat)
                    results.append(result)
                    output.write(json.dumps(result) + "\n")
                    output.flush()
                    print_result(result)
    except APIError as exc:
        print(
            f"Model API failure: {type(exc).__name__} "
            f"(status {getattr(exc, 'status_code', None)}). Experiment stopped.",
            file=sys.stderr,
        )
        return 1
    print_summary(results, scenarios)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ValueError as exc:
        print(f"Configuration or response error: {exc}", file=sys.stderr)
        sys.exit(1)
