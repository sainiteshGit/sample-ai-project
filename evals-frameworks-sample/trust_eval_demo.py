"""Offline examples for learning how to interpret an eval score.

Run everything: python3 trust_eval_demo.py
Run one topic: python3 trust_eval_demo.py --demo confidence
Change the random draw: python3 trust_eval_demo.py --seed 7

Simulated pass/fail outcomes and constructed examples, not real LLM results.
Uses only the Python standard library. No API key or dependencies needed.
"""

import argparse
import math
import random


def run_trials(rate: float, n: int, rng: random.Random) -> int:
    return sum(rng.random() < rate for _ in range(n))


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


def heading(title: str) -> None:
    print(f"\n{title}\n{'=' * len(title)}")


def demo_variation(seed: int) -> None:
    heading("1. Same system, different measured scores")
    print("SIMULATION: true pass probability stays at 90%.")
    print("One case, 20 independent attempts per batch.\n")
    rng = random.Random(seed)
    total = 0
    for batch in range(1, 6):
        passes = run_trials(0.90, 20, rng)
        total += passes
        print(f"Batch {batch}: {passes:2}/20 = {passes / 20:5.1%}")
    print(f"\nCombined: {total}/100 = {total / 100:.1%}")
    print("Nothing changed. Different samples can give different scores.")
    print("This says nothing about coverage of other requests.")


def demo_confidence() -> None:
    heading("2. Same measured rate, different uncertainty")
    print("CONSTRUCTED COUNTS: hold the rate at 90% and increase N.")
    print("Assumption: independent trials with a fixed pass probability.\n")
    print(f"{'Passes/N':>12}  {'Rate':>6}  {'95% Wilson interval':>23}")
    for passes, n in ((90, 100), (900, 1000), (9000, 10000)):
        low, high = wilson_interval(passes, n)
        print(f"{passes:>6}/{n:<5}  {passes / n:6.1%}  "
              f"{low:9.1%} to {high:6.1%}")
    low, high = wilson_interval(10, 10)
    print(f"\n10/10 passes = 100%, but its interval is {low:.1%} to {high:.1%}.")
    print("Ten successes do not prove perfect reliability.")
    print("More independent trials generally narrow the interval.")
    print("About 4x the trials gives roughly half the uncertainty.")
    print("95% describes the interval method's repeated-sampling coverage;")
    print("it does not mean 95% of future answers will pass.")


def demo_compare(seed: int) -> None:
    heading("3. Can a small experiment identify the better version?")
    print("SIMULATION: A truly passes 88%; B truly passes 91%.")
    print("Each experiment samples both versions independently.")
    print("Repeat the whole experiment 100 times at each sample size.\n")
    print(f"{'N/version':>10}  {'A wins':>8}  {'Ties':>8}  {'B wins':>8}")
    rng = random.Random(seed)
    experiments = 100
    for n in (20, 100, 500, 2000):
        a_wins = ties = b_wins = 0
        for _ in range(experiments):
            a = run_trials(0.88, n, rng)
            b = run_trials(0.91, n, rng)
            if a > b:
                a_wins += 1
            elif b > a:
                b_wins += 1
            else:
                ties += 1
        print(f"{n:10}  {a_wins:8}  {ties:8}  {b_wins:8}")
    print("\nA win means only a higher observed rate, not significance.")
    print("These counts are simulation frequencies, not p-values.")
    print("Even 100/100 observed wins would not guarantee future wins.")
    print("Real version comparisons should use matched cases and assess")
    print("uncertainty in the difference, not just interval overlap.")


def demo_distribution() -> None:
    heading("4. Same average, different failure patterns")
    print("CONSTRUCTED COUNTS: five cases, ten attempts each.\n")
    cases = (
        "Standard booking",
        "Cancellation",
        "Large party",
        "Ambiguous date",
        "Closed Monday",
    )
    a_passes = (8, 8, 8, 8, 8)
    b_passes = (10, 10, 10, 10, 0)
    print(f"{'Case':<20}  {'A passes':>8}  {'B passes':>8}")
    for case, a, b in zip(cases, a_passes, b_passes):
        print(f"{case:<20}  {a:5}/10  {b:5}/10")
    attempts = len(cases) * 10
    a_total = sum(a_passes)
    b_total = sum(b_passes)
    print(f"\nA: {a_total}/{attempts} = {a_total / attempts:.0%}")
    print(f"B: {b_total}/{attempts} = {b_total / attempts:.0%}")
    print("B fails every closed-Monday attempt in this example.")
    print("More repeats on the other cases will not uncover that gap.")
    print("Inspect categories as well as the average.")
    print("Here, consistency means all ten pass/fail labels agree:")
    print("B is consistent on every case, including the all-fail case.")
    print("Consistency is not correctness.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--demo",
        choices=("all", "variation", "confidence", "compare", "distribution"),
        default="all",
        help="Show all examples or one topic for a screenshot.",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print("TRUSTING AN EVAL SCORE")
    print("Offline teaching demo. No LLM calls. No judge model.")
    print(f"Random seed: {args.seed}")
    if args.demo in ("all", "variation"):
        demo_variation(args.seed)
    if args.demo in ("all", "confidence"):
        demo_confidence()
    if args.demo in ("all", "compare"):
        demo_compare(args.seed)
    if args.demo in ("all", "distribution"):
        demo_distribution()


if __name__ == "__main__":
    main()
