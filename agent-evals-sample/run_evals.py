#!/usr/bin/env python3
"""
Evaluation Harness — Restaurant Reservation Agent
================================================

Evaluates a Restaurant Reservation Agent using a structured approach:

  Eval Suite → Tasks → Trials → Graders → Metrics

Grader types (from the article):`
  - deterministic_tests : Fast, cheap, objective, reproducible.
  - state_check         : Outcome verification (keywords in the reservation).
  - llm_rubric          : LLM-as-judge for tone, helpfulness, nuance.

Usage:
  python run_evals.py                             # all tasks, 1 trial
  python run_evals.py --trials 3                  # 3 trials (for pass@k / pass^k)
  python run_evals.py --task book_saturday_dinner
  python run_evals.py --type capability
  python run_evals.py --with-llm-grader           # enable LLM rubric grading
  python run_evals.py --output results.json
"""

import sys, json, argparse
from pathlib import Path
from datetime import datetime, timezone

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from agent import handle_reservation, Reservation


# ═══════════════════════════════════════════════════════════════════════════
# GRADER: deterministic_tests
# ═══════════════════════════════════════════════════════════════════════════
# Anthropic: "Code-based graders — fast, cheap, objective, reproducible."

def run_deterministic_tests(output: Reservation | None, grader_config: dict) -> dict:
    """
    Run typed checks on the structured Reservation output.

    Supported checks:
      {field: "status", equals: "confirmed"}
      {field: "status", in: ["confirmed", "waitlisted"]}
      {field: "party_size", equals: 4}
      {field: "time", contains: "7"}
      {field: "special_requests", min_count: 2}
    """
    checks = grader_config.get("checks", [])
    results = []

    for check in checks:
        field = check.get("field", "")
        passed = False
        detail = ""

        if output is None:
            results.append({"check": field, "pass": False, "detail": "No agent output"})
            continue

        val = getattr(output, field, None)

        if "equals" in check:
            expected = check["equals"]
            passed = val == expected
            detail = f"'{val}' {'==' if passed else '!='} '{expected}'"

        elif "in" in check:
            allowed = check["in"]
            passed = val in allowed
            detail = f"'{val}' {'∈' if passed else '∉'} {allowed}"

        elif "contains" in check:
            substr = str(check["contains"]).lower()
            passed = substr in str(val).lower()
            detail = f"'{val}' {'contains' if passed else 'missing'} '{substr}'"

        elif "min_count" in check:
            n = len(val) if isinstance(val, list) else 0
            passed = n >= check["min_count"]
            detail = f"{n} items (need >= {check['min_count']})"

        else:
            detail = f"Unknown check for field '{field}'"

        results.append({"check": field, "pass": passed, "detail": detail})

    n_passed = sum(r["pass"] for r in results)
    n_total = len(results)
    return {
        "grader": "deterministic_tests",
        "pass": n_passed == n_total,
        "score": n_passed / n_total if n_total else 0.0,
        "checks": results,
    }


# ═══════════════════════════════════════════════════════════════════════════
# GRADER: state_check
# ═══════════════════════════════════════════════════════════════════════════
# Anthropic: "The outcome is the final state in the environment."

def run_state_check(output: Reservation | None, grader_config: dict) -> dict:
    """Check keywords appear in the agent's message and special_requests."""
    expect = grader_config.get("expect", {})
    results = []

    if output is None:
        return {"grader": "state_check", "pass": False, "score": 0.0,
                "checks": [{"check": "output_exists", "pass": False, "detail": "No output"}]}

    # Combine all text fields for keyword search
    all_text = (
        f"{output.agent_message} "
        f"{' '.join(output.special_requests)} "
        f"{output.seating} {output.status}"
    ).lower()

    for kw in expect.get("keywords_in_output", []):
        found = kw.lower() in all_text
        results.append({
            "check": f"keyword:{kw}",
            "pass": found,
            "detail": f"'{kw}' {'found' if found else 'NOT found'}"
        })

    n_passed = sum(r["pass"] for r in results)
    n_total = len(results)
    return {
        "grader": "state_check",
        "pass": n_passed == n_total if n_total else True,
        "score": n_passed / n_total if n_total else 1.0,
        "checks": results,
    }


# ═══════════════════════════════════════════════════════════════════════════
# GRADER: llm_rubric
# ═══════════════════════════════════════════════════════════════════════════
# Anthropic: "LLM-as-judge graders should be closely calibrated with human
# experts... give the LLM a way out, like 'Unknown'."

LLM_JUDGE_SYSTEM = """\
You are an expert evaluator for a restaurant reservation agent.
Score each assertion as PASS, FAIL, or UNKNOWN.
Return ONLY valid JSON:
{
  "results": [
    {"assertion": "...", "verdict": "PASS|FAIL|UNKNOWN", "reasoning": "brief"}
  ]
}"""


def run_llm_rubric(output: Reservation | None, task: dict, grader_config: dict) -> dict:
    if output is None:
        return {"grader": "llm_rubric", "pass": False, "score": 0.0,
                "checks": [{"check": "output_exists", "pass": False, "detail": "No output"}]}

    assertions = grader_config.get("assertions", [])
    if not assertions:
        return {"grader": "llm_rubric", "pass": True, "score": 1.0, "checks": []}

    from agent import _get_client
    client, model = _get_client()

    output_json = output.model_dump_json(indent=2)
    prompt = f"""## Customer Request
{task.get('request', '')}

## Agent's Reservation Output
```json
{output_json}
```

## Assertions to evaluate
{json.dumps(assertions, indent=2)}

Evaluate each assertion. Return JSON."""

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": LLM_JUDGE_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        judge_output = json.loads(resp.choices[0].message.content)
        checks = []
        for r in judge_output.get("results", []):
            verdict = r.get("verdict", "UNKNOWN")
            checks.append({
                "check": r.get("assertion", "")[:60],
                "pass": verdict == "PASS",
                "detail": f"{verdict} — {r.get('reasoning', '')}"
            })

        n_passed = sum(c["pass"] for c in checks)
        return {
            "grader": "llm_rubric",
            "pass": n_passed == len(checks),
            "score": n_passed / len(checks) if checks else 0.0,
            "checks": checks,
        }
    except Exception as e:
        return {"grader": "llm_rubric", "pass": False, "score": 0.0,
                "checks": [{"check": "llm_judge_error", "pass": False, "detail": str(e)}]}


# ═══════════════════════════════════════════════════════════════════════════
# TRIAL — "Each attempt at a task is a trial"
# ═══════════════════════════════════════════════════════════════════════════

def run_trial(task: dict, trial_num: int, use_llm_grader: bool = False) -> dict:
    # Step 1: Run the agent
    output, metadata = handle_reservation(task["request"])

    # Step 2: Run graders
    grader_results = []
    for grader_def in task.get("graders", []):
        gtype = grader_def.get("type")
        if gtype == "deterministic_tests":
            grader_results.append(run_deterministic_tests(output, grader_def))
        elif gtype == "state_check":
            grader_results.append(run_state_check(output, grader_def))
        elif gtype == "llm_rubric" and use_llm_grader:
            grader_results.append(run_llm_rubric(output, task, grader_def))

    # Step 3: Compute overall (binary — all graders must pass)
    all_pass = all(g["pass"] for g in grader_results) if grader_results else False
    avg_score = sum(g["score"] for g in grader_results) / len(grader_results) if grader_results else 0.0

    # Step 4: Collect tracked_metrics
    tracked = {}
    for mg in task.get("tracked_metrics", []):
        for name in mg.get("metrics", []):
            tracked[name] = metadata.get(name, 0)

    return {
        "task_id": task["id"], "trial": trial_num,
        "pass": all_pass, "score": round(avg_score, 4),
        "graders": grader_results, "tracked_metrics": tracked,
        "error": metadata.get("error"),
    }


# ═══════════════════════════════════════════════════════════════════════════
# METRICS — pass@k and pass^k
# ═══════════════════════════════════════════════════════════════════════════

def compute_pass_at_k(trials: list[dict]) -> dict:
    k = len(trials)
    if k == 0:
        return {"pass_rate": 0, "pass_at_k": 0, "pass_power_k": 0, "avg_score": 0}
    p = sum(t["pass"] for t in trials) / k
    return {
        "num_trials": k,
        "num_passed": sum(t["pass"] for t in trials),
        "pass_rate": round(p, 4),
        "pass_at_k": round(1 - (1 - p) ** k, 4),
        "pass_power_k": round(p ** k, 4),
        "avg_score": round(sum(t["score"] for t in trials) / k, 4),
    }


# ═══════════════════════════════════════════════════════════════════════════
# REPORT
# ═══════════════════════════════════════════════════════════════════════════

G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[1m"; RST = "\033[0m"


def print_report(suite: dict):
    tasks = suite["task_results"]
    k = suite["trials_per_task"]

    print(f"\n{B}{'═'*76}")
    print(f"  EVAL SUITE: {suite['suite_name']}")
    print(f"  Run:    {suite['timestamp']}")
    print(f"  Trials: {k} per task    LLM grader: {'ON' if suite['llm_grader'] else 'OFF'}")
    print(f"{'═'*76}{RST}\n")

    hdr = f"  {'Task':<30} {'Type':<12} {'Pass':>5}  {'Score':>6}"
    if k > 1:
        hdr += f"  {'pass@k':>7}  {'pass^k':>7}"
    hdr += f"  {'Tokens':>7}  {'Latency':>8}"
    print(hdr)
    print(f"  {'─'*74}")

    for t in tasks:
        m = t["metrics"]
        c = G if m["pass_rate"] == 1 else (Y if m["pass_rate"] > 0 else R)
        row = f"  {c}{t['task_id']:<30}{RST} {t['type']:<12} {m['num_passed']}/{m['num_trials']:>2}  {m['avg_score']:>5.0%}"
        if k > 1:
            row += f"  {m['pass_at_k']:>6.0%}   {m['pass_power_k']:>6.0%}"
        row += f"  {t.get('avg_tokens', 0):>7.0f}  {t.get('avg_latency_ms', 0):>6.0f}ms"
        print(row)

    total_p = sum(t["metrics"]["num_passed"] for t in tasks)
    total_t = sum(t["metrics"]["num_trials"] for t in tasks)
    avg_s = sum(t["metrics"]["avg_score"] for t in tasks) / len(tasks) if tasks else 0
    print(f"  {'─'*74}")
    print(f"  {B}{'OVERALL':<30}{RST} {'':12} {total_p}/{total_t:>2}  {avg_s:>5.0%}")

    for eval_type in ("capability", "regression"):
        subset = [t for t in tasks if t["type"] == eval_type]
        if subset:
            sp = sum(t["metrics"]["num_passed"] for t in subset)
            st = sum(t["metrics"]["num_trials"] for t in subset)
            ss = sum(t["metrics"]["avg_score"] for t in subset) / len(subset)
            label = "Capability" if eval_type == "capability" else "Regression"
            print(f"    {label}: {sp}/{st} passed, avg score {ss:.0%}")

    # Failed checks
    fails = []
    for t in tasks:
        for trial in t["trials"]:
            if not trial["pass"]:
                for g in trial["graders"]:
                    if not g["pass"]:
                        for c in g.get("checks", []):
                            if not c["pass"]:
                                fails.append(
                                    f"    [{t['task_id']}] trial {trial['trial']} "
                                    f"| {g['grader']}.{c['check']} → {c['detail']}"
                                )

    if fails:
        print(f"\n  {R}FAILED CHECKS ({len(fails)}):{RST}")
        for f in fails[:15]:
            print(f)
    else:
        print(f"\n  {G}All checks passed!{RST}")

    print(f"\n{B}{'═'*76}{RST}\n")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(
        description="Anthropic-style eval harness for Restaurant Reservation Agent"
    )
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--task", type=str)
    ap.add_argument("--type", choices=["capability", "regression"])
    ap.add_argument("--with-llm-grader", action="store_true")
    ap.add_argument("--output", type=str)
    args = ap.parse_args()

    with open(Path(__file__).parent / "tasks.yaml") as f:
        tasks = yaml.safe_load(f)["tasks"]

    if args.task:
        tasks = [t for t in tasks if t["id"] == args.task]
        if not tasks:
            print(f"Error: task '{args.task}' not found"); sys.exit(1)
    if args.type:
        tasks = [t for t in tasks if t.get("type") == args.type]

    n_runs = len(tasks) * args.trials
    print(f"\n{B}Running {len(tasks)} tasks x {args.trials} trial(s) = {n_runs} runs{RST}")
    if args.with_llm_grader:
        print(f"  LLM rubric grader: ON")
    print()

    task_results = []
    for i, task in enumerate(tasks):
        print(f"[{i+1}/{len(tasks)}] {task['id']}: {task['desc']}")

        trials = []
        for n in range(1, args.trials + 1):
            trial = run_trial(task, n, use_llm_grader=args.with_llm_grader)
            trials.append(trial)

            status = f"{G}PASS{RST}" if trial["pass"] else f"{R}FAIL{RST}"
            tok = trial["tracked_metrics"].get("n_total_tokens", 0)
            lat = trial["tracked_metrics"].get("time_to_last_token", 0)
            print(f"  trial {n} -> {status}  score={trial['score']:.0%}  "
                  f"tokens={tok}  latency={lat:.0f}ms")

        metrics = compute_pass_at_k(trials)
        avg_tokens = sum(t["tracked_metrics"].get("n_total_tokens", 0) for t in trials) / len(trials)
        avg_latency = sum(t["tracked_metrics"].get("time_to_last_token", 0) for t in trials) / len(trials)

        task_results.append({
            "task_id": task["id"], "type": task.get("type", "capability"),
            "desc": task["desc"], "metrics": metrics,
            "avg_tokens": avg_tokens, "avg_latency_ms": avg_latency,
            "trials": trials,
        })

    suite = {
        "suite_name": "Restaurant Reservation Agent Evals",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trials_per_task": args.trials,
        "llm_grader": args.with_llm_grader,
        "task_results": task_results,
    }

    print_report(suite)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(suite, f, indent=2, default=str)
        print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
