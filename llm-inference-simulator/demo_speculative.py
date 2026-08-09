"""
Demo: Speculative decoding  (module 01, concept 4)
Show the draft->verify->accept/reject loop AND prove, empirically, that the
emitted tokens follow the TARGET distribution exactly -- regardless of how bad
the draft model is.  Pure Python, no numpy.

Run:  python3 demo_speculative.py

Two parts:
  PART A  one verification round, printed step by step (why min(1,p/q) + resample)
  PART B  run the full scheme 200k times and show the output histogram == target
"""
import random

random.seed(0)

VOCAB = ["Paris", "Lyon", "Nice", "Metz"]

# TARGET distribution p (the big model -- the source of truth we must match)
P = {"Paris": 0.70, "Lyon": 0.20, "Nice": 0.07, "Metz": 0.03}
# DRAFT distribution q (the small model -- deliberately WRONG to prove the point)
Q = {"Paris": 0.40, "Lyon": 0.40, "Nice": 0.10, "Metz": 0.10}


def sample(dist):
    r = random.random()
    c = 0.0
    for tok, prob in dist.items():
        c += prob
        if r < c:
            return tok
    return list(dist)[-1]


def residual(P, Q):
    """corrected distribution = normalize(max(0, p - q))."""
    raw = {t: max(0.0, P[t] - Q[t]) for t in P}
    s = sum(raw.values())
    if s == 0:                       # fall back to target if no residual mass
        return dict(P)
    return {t: v / s for t, v in raw.items()}


def speculative_token():
    """One drafted token, verified against the target. Returns the emitted token."""
    d = sample(Q)                    # draft proposes
    accept_prob = min(1.0, P[d] / Q[d])
    if random.random() < accept_prob:
        return d, True               # accepted the draft's guess
    else:
        return sample(residual(P, Q)), False   # reject -> resample corrected


# --- PART A: one round, shown step by step ---------------------------------
print("#" * 70)
print("# PART A - one verification round (k=4 drafted tokens)")
print("#" * 70)
print(f"target p = {P}")
print(f"draft  q = {Q}\n")
print(f"{'drafted':<8}{'q':>6}{'p':>6}{'accept=min(1,p/q)':>20}{'result':>22}")
print("-" * 62)
random.seed(3)
accepted = 0
for _ in range(4):
    d = sample(Q)
    ap = min(1.0, P[d] / Q[d])
    r = random.random()
    if r < ap:
        print(f"{d:<8}{Q[d]:>6.2f}{P[d]:>6.2f}{ap:>20.2f}{'ACCEPT '+d:>22}")
        accepted += 1
    else:
        rs = sample(residual(P, Q))
        print(f"{d:<8}{Q[d]:>6.2f}{P[d]:>6.2f}{ap:>20.2f}{'reject->'+rs+' (STOP)':>22}")
        break
print(f"\n-> {accepted} token(s) accepted before first rejection")
print("   (everything after the first rejection is discarded and redrafted)")

# --- PART B: empirical proof the OUTPUT == TARGET distribution --------------
print("\n" + "#" * 70)
print("# PART B - run 200,000 emitted tokens: does the output match TARGET?")
print("#" * 70)
random.seed(0)
TRIALS = 200_000
counts = {t: 0 for t in VOCAB}
n_accept = 0
for _ in range(TRIALS):
    tok, was_accepted = speculative_token()
    counts[tok] += 1
    n_accept += was_accepted

print(f"\n{'token':<8}{'target p':>10}{'draft q':>10}{'emitted freq':>15}")
print("-" * 43)
for t in VOCAB:
    print(f"{t:<8}{P[t]:>10.3f}{Q[t]:>10.3f}{counts[t]/TRIALS:>15.3f}")

print(f"\ndraft acceptance rate: {n_accept/TRIALS:.1%}  (draft was deliberately bad)")
print("\nTakeaways:")
print("  * emitted frequency matches TARGET p, NOT draft q -> output is exact")
print("  * the draft's q cancels out in the math (min(1,p/q) + residual resample)")
print("  * a bad draft only lowers the acceptance rate (less speedup),")
print("    it NEVER changes the output distribution -> quality is guaranteed")
