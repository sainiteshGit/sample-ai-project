"""
simple_eval_demo.py  —  the whole idea of evals, in numbers.
No API key, no libraries.

    python3 simple_eval_demo.py
"""

import random

random.seed(42)  # same numbers every run

# An LLM call is a coin, not a function: this one is "correct" 90% of the time.
def run_once() -> bool:
    return random.random() < 0.90

# 1. one run
print("1 run        :", "PASS" if run_once() else "FAIL")

# 2. many runs -> real success rate
passes = sum(run_once() for _ in range(100))
print("100 runs     :", f"{passes}/100 = {passes}%")

# 3. pass@k vs pass^k
any_of_5 = sum(any(run_once() for _ in range(5)) for _ in range(1000)) / 1000
all_of_5 = sum(all(run_once() for _ in range(5)) for _ in range(1000)) / 1000
print("pass@5 (any) :", f"{any_of_5:.0%}")
print("pass^5 (all) :", f"{all_of_5:.0%}")

# 4. compounding over a pipeline
print("0.9 ^ 20     :", f"{0.90 ** 20:.0%}")
