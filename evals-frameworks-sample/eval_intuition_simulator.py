#!/usr/bin/env python3
"""
Eval Intuition Simulator  (no API key, pure stdlib)
===================================================
The blog's claim is abstract: "an LLM call is a random variable, so correctness
is a statistic, not a property." This script makes that *visible* on a laptop.

We model one eval case as a coin: a Bernoulli(p) random variable with a true
(hidden) success rate p. We never "know" p directly -- we only get to sample it,
exactly like calling a real model. Every lesson below falls out of that one idea.

Concepts (each is a --demo):
  n1        The N=1 lie: one trial tells you almost nothing about p.
  passk     pass-rate vs pass@k vs pass^k -- why "which k" changes the verdict.
  consistency  Two systems, same mean, different spread (consistency@k).
  compound  Per-step 0.9 -> ~0.12 over 20 steps. Reliability compounds.
  drift     A frozen suite goes red when p moves under you.
  all       Run everything (default).

Usage:
  python eval_intuition_simulator.py                 # all demos, fixed seed
  python eval_intuition_simulator.py --demo passk
  python eval_intuition_simulator.py --demo compound --steps 20 --p 0.9
  python eval_intuition_simulator.py --seed 7 --trials 200

Nothing here calls a model. The randomness is a coin flip so you can focus on the
STATISTICS, which are the genuinely hard part of evals.
"""

import argparse
import math
import random
import statistics


# ── tiny ASCII helpers ────────────────────────────────────────────────────────
def bar(frac: float, width: int = 40, fill: str = "#") -> str:
    frac = max(0.0, min(1.0, frac))
    n = round(frac * width)
    return fill * n + "." * (width - n)


def rule(title: str) -> None:
    print("\n" + "=" * 72)
    print(f"  {title}")
    print("=" * 72)


# ── the "model": one case is a coin with hidden true rate p ──────────────────
def trial(p: float, rng: random.Random) -> bool:
    """One eval run of one case. True = passed. This is our stand-in for an LLM call."""
    return rng.random() < p


def wilson_ci(passes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson interval for a proportion -- honest error bars, good for small n."""
    if n == 0:
        return (0.0, 1.0)
    phat = passes / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = (z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, center - half), min(1.0, center + half))


# ── DEMO 1: the N=1 lie ──────────────────────────────────────────────────────
def demo_n1(p: float, rng: random.Random, max_n: int) -> None:
    rule(f"1) The N=1 lie   (true hidden p = {p:.2f})")
    print("One run 'passes' or 'fails' -- but that says almost nothing about p.")
    print("Watch the estimate + 95% error bar tighten as N grows (~1/sqrt(N)).\n")
    print(f"  {'N':>6}  {'passes':>7}  {'est. rate':>9}  {'95% CI':>16}  width")
    passes = 0
    ns = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000]
    ns = [n for n in ns if n <= max_n] or [max_n]
    prev = 0
    for n in ns:
        for _ in range(n - prev):
            passes += 1 if trial(p, rng) else 0
        prev = n
        lo, hi = wilson_ci(passes, n)
        print(f"  {n:>6}  {passes:>7}  {passes/n:>8.1%}  [{lo:>5.1%},{hi:>5.1%}]  {hi-lo:>6.1%}")
    print("\n  Takeaway: N=1 is a single sample, not a proof. Precision ~ sqrt(N):")
    print("  to halve the error bar you need 4x the data.")


# ── DEMO 2: pass-rate vs pass@k vs pass^k ────────────────────────────────────
def demo_passk(p: float, rng: random.Random, trials: int) -> None:
    rule(f"2) pass-rate vs pass@k vs pass^k   (true p = {p:.2f})")
    print("Same system, three different questions:")
    print("  pass-rate : chance a single run passes            = p")
    print("  pass@k    : chance AT LEAST ONE of k runs passes  = 1-(1-p)^k   (retry-friendly)")
    print("  pass^k    : chance ALL k runs pass                = p^k         (consistency-strict)\n")
    print(f"  {'k':>3}  {'pass@k (any)':>14}  {'pass^k (all)':>14}   pass^k bar")
    for k in range(1, 9):
        pak = 1 - (1 - p) ** k
        ppk = p ** k
        print(f"  {k:>3}  {pak:>13.1%}  {ppk:>13.1%}   {bar(ppk)}")
    # empirical check so it's not just formulas
    got_any = got_all = 0
    for _ in range(trials):
        runs = [trial(p, rng) for _ in range(5)]
        got_any += any(runs)
        got_all += all(runs)
    print(f"\n  Empirical over {trials} draws of k=5:  pass@5 ~ {got_any/trials:.1%}"
          f"  (formula {1-(1-p)**5:.1%}),  pass^5 ~ {got_all/trials:.1%}"
          f"  (formula {p**5:.1%})")
    print("  Takeaway: an agent that can retry cares about pass@k; an agent that")
    print("  must be right every step cares about pass^k. Report the one you live by.")


# ── DEMO 3: consistency@k -- same mean, different spread ──────────────────────
def demo_consistency(rng: random.Random, trials: int, k: int) -> None:
    rule("3) Consistency@k   (two systems, SAME mean, different spread)")
    print("System A: every case has p=0.80  (uniformly a bit flaky).")
    print("System B: half the cases p=1.00, half p=0.60  (mean still 0.80).")
    print(f"Run each case k={k} times; 'consistent' = all k agree (all pass or all fail).\n")

    def run_system(case_ps: list[float]) -> tuple[float, float]:
        mean_pass, consistent = 0, 0
        for _ in range(trials):
            cp = rng.choice(case_ps)
            runs = [trial(cp, rng) for _ in range(k)]
            mean_pass += sum(runs) / k
            consistent += 1 if (all(runs) or not any(runs)) else 0
        return mean_pass / trials, consistent / trials

    a_mean, a_cons = run_system([0.80])
    b_mean, b_cons = run_system([1.00, 0.60])
    print(f"  {'system':>8}  {'mean pass':>10}  {'consistency@k':>14}")
    print(f"  {'A':>8}  {a_mean:>9.1%}  {a_cons:>13.1%}   {bar(a_cons)}")
    print(f"  {'B':>8}  {b_mean:>9.1%}  {b_cons:>13.1%}   {bar(b_cons)}")
    print("\n  Takeaway: identical average, different reliability. A single mean hides")
    print("  variance -- consistency@k is what tells flaky-everywhere from split-personality.")


# ── DEMO 4: compounding ──────────────────────────────────────────────────────
def demo_compound(p: float, steps: int, rng: random.Random, trials: int) -> None:
    rule(f"4) Compounding   (per-step p = {p:.2f}, chained {steps} steps)")
    print("A pipeline succeeds only if EVERY step succeeds: end-to-end = p^n.\n")
    print(f"  {'steps':>5}  {'end-to-end':>11}   bar")
    for n in [1, 2, 3, 5, 10, 15, 20, 30, 50]:
        if n > steps and n != 50:
            continue
        e2e = p ** n
        print(f"  {n:>5}  {e2e:>10.1%}   {bar(e2e)}")
    # empirical for the requested depth
    ok = 0
    for _ in range(trials):
        ok += 1 if all(trial(p, rng) for _ in range(steps)) else 0
    print(f"\n  Empirical: a {steps}-step agent at {p:.0%}/step succeeds "
          f"{ok/trials:.1%} of the time (formula {p**steps:.1%}).")
    print(f"  Takeaway: a '{p:.0%} component' is a {p**steps:.0%} pipeline at {steps} steps.")
    print("  Silent 1-in-10 errors that never throw are why agents quietly fail.")


# ── DEMO 5: drift ────────────────────────────────────────────────────────────
def demo_drift(rng: random.Random, trials: int, threshold: float) -> None:
    rule(f"5) Drift   (frozen suite, gate = pass-rate >= {threshold:.0%})")
    print("Your code and prompt are frozen. The provider nudges the model, so the")
    print("hidden p moves. Nothing in YOUR repo changed -- watch the gate flip.\n")
    print(f"  {'month':>5}  {'true p':>7}  {'measured':>9}  {'95% CI':>16}  gate")
    schedule = [0.93, 0.92, 0.93, 0.89, 0.86, 0.90]
    for month, p in enumerate(schedule):
        passes = sum(1 if trial(p, rng) else 0 for _ in range(trials))
        rate = passes / trials
        lo, hi = wilson_ci(passes, trials)
        # gate on the lower CI bound -- the statistically honest choice
        ok = lo >= threshold
        print(f"  {month:>5}  {p:>6.2f}  {rate:>8.1%}  [{lo:>5.1%},{hi:>5.1%}]  "
              f"{'PASS' if ok else 'FAIL <-- regression, no code change'}")
    print("\n  Takeaway: a unit test would stay green (nothing to re-run). Only a")
    print("  SCHEDULED eval catches drift -- that's why online/continuous evals exist.")


def main() -> None:
    ap = argparse.ArgumentParser(description="No-API simulator for eval statistics.")
    ap.add_argument("--demo", default="all",
                    choices=["all", "n1", "passk", "consistency", "compound", "drift"])
    ap.add_argument("--seed", type=int, default=42, help="reproducible randomness")
    ap.add_argument("--p", type=float, default=0.90, help="true per-case/per-step rate")
    ap.add_argument("--trials", type=int, default=2000, help="samples for empirical demos")
    ap.add_argument("--steps", type=int, default=20, help="pipeline depth for compound")
    ap.add_argument("--k", type=int, default=5, help="repeats for consistency@k")
    ap.add_argument("--threshold", type=float, default=0.90, help="drift gate")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    print(f"seed={args.seed}  (reproducible; change --seed to resample)")

    if args.demo in ("all", "n1"):
        demo_n1(args.p, rng, args.trials)
    if args.demo in ("all", "passk"):
        demo_passk(args.p, rng, args.trials)
    if args.demo in ("all", "consistency"):
        demo_consistency(rng, args.trials, args.k)
    if args.demo in ("all", "compound"):
        demo_compound(args.p, args.steps, rng, args.trials)
    if args.demo in ("all", "drift"):
        demo_drift(rng, args.trials, args.threshold)
    print()


if __name__ == "__main__":
    main()
