"""
online_eval_demo.py — monitoring a stochastic process in production.

Offline eval = CI test bench (frozen golden set, known answers).
Online  eval = production monitoring (live traffic, NO answer key).

This demo is OFFLINE and needs NO API key. It simulates a live traffic stream
and runs the five online-eval tools on it, then injects SILENT DRIFT to show
why you can't trust a passing CI suite forever.

The stream models the reservation assistant. Every call gets:
  1. CHEAP GRADER (100% of traffic): is it valid JSON with a booking status? Free.
  2. SAMPLED JUDGE (5% of traffic): a reference-free rubric score (no answer key).
  3. DRIFT ALARM: roll the judge score over a window; page when it breaks the SLO.
  4. USER SIGNAL: thumbs-down on bad replies (ground truth arriving late).
  5. FEEDBACK LOOP: a drifting trace is promoted into a NEW golden case offline.

At call 1000 we silently degrade the model (a "provider update"). HTTP still
returns 200. Nothing throws. Watch the alarm catch it while CI stays green.

    python3 online_eval_demo.py
    python3 online_eval_demo.py --seed 7 --drift-at 800 --calls 1500
"""

import argparse
import json
import random


# --- the production model, as a coin ---------------------------------------
# pre_drift_quality:  chance a reply is genuinely good BEFORE the silent change
# post_drift_quality: chance a reply is good AFTER (the provider updated it)
#
# "good" here = polite + declined-closed + suggested-another-day, judged on the
# meaning, not an exact string. There is no golden answer to diff against.


def make_reply(rng: random.Random, quality: float) -> dict:
    """One production call. Returns a fake trace record."""
    good = rng.random() < quality
    if good:
        reply = (
            "We're closed Mondays — could I book you Tuesday at 7 PM instead?"
        )
    else:
        # silently worse: still valid JSON, still HTTP 200, but unhelpful/cold
        reply = rng.choice(
            [
                "Sure, see you Monday at 7!",   # wrong: books a closed day
                "Closed. Next.",                # rude, no alternative
                "Try again later.",             # dismissive
            ]
        )
    # every call is HTTP 200 with well-formed JSON — the cheap grader passes
    record = {
        "status_code": 200,
        "valid_json": True,
        "status": "declined" if good else rng.choice(["confirmed", "declined"]),
        "reply": reply,
        "good": good,  # hidden ground truth the monitors DON'T see
        "tokens": rng.randint(18, 30),
        "latency_ms": rng.randint(120, 400),
    }
    return record


# --- the five online-eval tools --------------------------------------------

def cheap_grader(record: dict) -> bool:
    """Reference-free oracle: format/status shape. Runs on 100% of traffic.
    Cheap and honest about format, blind to tone and correctness."""
    return record["status_code"] == 200 and record["valid_json"]


def rubric_score(record: dict) -> float:
    """A sampled reference-free judge. No answer key; it checks the policy:
    declined-the-closed-day AND offered-another-day AND polite tone.
    In a real system this is an LLM judge on 5% of traffic. Here we stand in
    with a deterministic proxy so the demo is offline and reproducible.
    Returns 0..1 (we add a little noise so it feels stochastic)."""
    base = 1.0 if record["good"] else 0.2
    return base  # deterministic here; the lesson is the sampling, not the judge


def rolling_mean(values: list[float], window: int) -> float:
    return sum(values[-window:]) / len(values[-window:])


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--calls", type=int, default=1500, help="traffic volume")
    p.add_argument("--drift-at", type=int, default=1000, help="call where quality silently drops")
    p.add_argument("--pre", type=float, default=0.92, help="good-rate before drift")
    p.add_argument("--post", type=float, default=0.55, help="good-rate after drift")
    p.add_argument("--sample-rate", type=float, default=0.05, help="judge sampling")
    p.add_argument("--window", type=int, default=20, help="drift-alarm window")
    p.add_argument("--slo", type=float, default=0.85, help="min rolling judge score")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    if args.drift_at >= args.calls:
        p.error("--drift-at must be less than --calls")

    rng = random.Random(args.seed)
    print("ONLINE EVAL: production monitoring on live traffic (no answer key)")
    print(f"calls={args.calls}  drift at call {args.drift_at}  "
          f"quality {args.pre:.0%} -> {args.post:.0%}  (silent)")
    print(f"cheap grader on 100% | judge on {args.sample_rate:.0%} sample | "
          f"alarm SLO={args.slo:.0%} over window={args.window}\n")

    judged: list[tuple[int, float]] = []
    rolling: list[float] = []
    cheap_fail = 0
    thumbs_down = 0
    alarm_call = None
    golden_additions = []

    for i in range(1, args.calls + 1):
        quality = args.pre if i < args.drift_at else args.post
        rec = make_reply(rng, quality)

        # tool 1: cheap grader on everything
        if not cheap_grader(rec):
            cheap_fail += 1

        # tool 2: sampled reference-free judge
        if rng.random() < args.sample_rate:
            score = rubric_score(rec)
            judged.append((i, score))
            rolling.append(score)

            # tool 3: drift alarm on the rolling judge score
            if alarm_call is None and len(rolling) >= args.window:
                if rolling_mean(rolling, args.window) < args.slo:
                    alarm_call = i
                    print(f"  >>> DRIFT ALARM fired at call {i}: "
                          f"rolling judge score fell below SLO {args.slo:.0%}")

            # tool 5: a clearly-bad sampled trace becomes a new offline case
            if score < 0.3 and len(golden_additions) < 3:
                golden_additions.append((i, rec["reply"]))

        # tool 4: users notice the bad replies (late ground truth)
        if not rec["good"] and rng.random() < 0.6:
            thumbs_down += 1

    # the catch: the cheap grader saw NOTHING. HTTP 200 and valid JSON throughout.
    pre_judged = [s for i, s in judged if i < args.drift_at]
    post_judged = [s for i, s in judged if i >= args.drift_at]

    print("\n--- what each tool saw ---")
    print(f"cheap grader (100% of traffic): {cheap_fail} failures "
          f"(HTTP 200 + valid JSON the whole time — it can't see meaning)")
    print(f"sampled judge: {len(judged)} graded "
          f"({args.sample_rate:.0%} of {args.calls})")
    print(f"  before drift : avg {sum(pre_judged)/len(pre_judged):.2f}")
    print(f"  after  drift : avg {sum(post_judged)/len(post_judged):.2f}")
    print(f"user thumbs-down received: {thumbs_down} (users felt it first)")
    print(f"drift alarm fired at call : {alarm_call}")

    print("\n--- the loop closes ---")
    print(f"{len(golden_additions)} drifting traces promoted to the offline golden set:")
    for call, reply in golden_additions:
        print(f"  golden case #{call}: expected=decline+alternative  got: {reply!r}")
    print("CI now fails on these until you fix it. The pager found it; the suite keeps it.")

    print("\nThe point: the offline suite stayed green. Production drifted anyway.")
    print("You needed traces, a sampled judge, and a drift alarm to see it.")


if __name__ == "__main__":
    main()
