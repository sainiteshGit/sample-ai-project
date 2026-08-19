"""
constrained.py -- Why 'please return JSON' breaks, and how constrained
decoding fixes it.

Module 02 - Context Engineering, Lesson 6.

Two failure modes of naive "respond only with JSON":
  1. The model is a probability machine -> sometimes emits fences/preamble/
     trailing commas -> parse error.
  2. finish_reason == "length": hitting the token limit mid-object leaves a
     SYNTAX ERROR, not a slightly-short answer. A fat input context (Lessons
     1-2) causes this by starving the output budget.

The fix is NOT a better prompt. It's constraining the SAMPLER: at each step,
compile the schema into a grammar/state-machine, compute which tokens are
LEGAL next, and mask (zero) every illegal token before sampling. The model
literally cannot emit invalid JSON.

This is a simulation of that masking behavior in pure Python. Run:
  python3 constrained.py
"""

import json
import random

# A tiny "vocabulary" of output fragments the model might emit each step.
# Some are junk (fences, preamble, trailing comma) that break JSON parsing.
JUNK = ["```json", "Sure, here is the JSON:", ",}", "\n\n", "```"]

# The target object we want the model to produce.
TARGET = {"name": "Alice", "tier": "premium", "open_tickets": 3}


# ---------------- unconstrained generation ----------------
def generate_unconstrained(token_budget, seed):
    """Free sampling: builds the right JSON but with some probability injects
    junk tokens, and hard-stops if it exceeds the token budget (finish_reason
    == length)."""
    rng = random.Random(seed)
    out = ""
    # maybe a preamble (the classic "Sure, here's..." leak)
    if rng.random() < 0.4:
        out += rng.choice(["```json\n", "Sure, here is the JSON:\n"])
    # emit the object piece by piece, char-budgeted
    body = json.dumps(TARGET)
    # maybe corrupt with a trailing comma before the closing brace
    if rng.random() < 0.3:
        body = body[:-1] + ",}"
    out += body
    if rng.random() < 0.3:
        out += "\n```"
    # enforce token (char) budget -> truncation
    finish = "stop"
    if len(out) > token_budget:
        out = out[:token_budget]
        finish = "length"
    return out, finish


# ---------------- constrained generation ----------------
# A minimal JSON state machine for our fixed schema. At each state only certain
# next fragments are legal; everything else is masked out (prob -> 0).
def generate_constrained(token_budget, seed):
    """Grammar-masked sampling: only legal fragments can be emitted, so the
    output is always valid + schema-conforming. If the budget is too small the
    grammar still forces a syntactically-closed object (best effort)."""
    # The legal, ordered emission plan derived from the schema/state machine.
    # (In a real system this is computed per-step from the automaton; here we
    # precompute the only legal path for the fixed schema.)
    plan = [
        '{', '"name"', ':', '"Alice"', ',',
        '"tier"', ':', '"premium"', ',',
        '"open_tickets"', ':', '3', '}'
    ]
    out = ""
    for frag in plan:
        # illegal tokens (JUNK) are masked -> can never be chosen. We only ever
        # append the legal next fragment.
        if len(out) + len(frag) > token_budget:
            # forced-close: emit whatever is needed to keep it valid JSON.
            # close any open string/braces minimally.
            if not out.endswith("}"):
                out = out.rstrip(",") 
                out += "}"
            return out, "length-but-valid"
        out += frag
    return out, "stop"


def try_parse(s):
    try:
        json.loads(s)
        return True, ""
    except Exception as e:
        return False, str(e)[:50]


def trial(label, gen, token_budget, runs=6):
    print("=" * 72)
    print(f"  {label}   (token_budget = {token_budget})")
    print("=" * 72)
    ok = 0
    for seed in range(runs):
        text, finish = gen(token_budget, seed)
        parsed, err = try_parse(text)
        ok += parsed
        shown = text.replace("\n", "\\n")
        if len(shown) > 46:
            shown = shown[:46] + "..."
        status = "PARSES  " if parsed else "BROKEN  "
        print(f"   seed {seed}: [{status}] finish={finish:<16} {shown}")
        if not parsed:
            print(f"            -> parse error: {err}")
    print(f"   >>> {ok}/{runs} valid JSON")
    print()
    return ok, runs


if __name__ == "__main__":
    print("Target object:", json.dumps(TARGET))
    print()

    # Generous budget: unconstrained still leaks junk sometimes.
    trial("UNCONSTRAINED ('please return JSON') -- generous budget",
          generate_unconstrained, token_budget=100)

    # Tight budget: unconstrained hits finish_reason=length -> broken mid-object.
    trial("UNCONSTRAINED -- TIGHT budget (starved output) -> finish_reason=length",
          generate_unconstrained, token_budget=20)

    # Constrained decoding: always valid, even under a tight budget.
    trial("CONSTRAINED (grammar masks illegal tokens) -- generous budget",
          generate_constrained, token_budget=100)

    trial("CONSTRAINED -- TIGHT budget: still valid (grammar force-closes)",
          generate_constrained, token_budget=20)

    print("=" * 72)
    print("  TAKEAWAY")
    print("=" * 72)
    print("  - Unconstrained: prompt can't guarantee validity; junk + truncation break it.")
    print("  - finish_reason=length turns a fat context into BROKEN output (Lessons 1-2).")
    print("  - Constrained decoding masks illegal tokens -> always parses.")
    print("  - Still reserve output budget: constraint prevents corruption,")
    print("    budgeting prevents truncation. You need BOTH.")
