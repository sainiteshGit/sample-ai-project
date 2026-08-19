"""
budget.py -- Token budgeting as a fixed-size allocator.

Module 02 - Context Engineering, Lesson 2.

The context window is a fixed pool of tokens shared by everything the model
needs: system prompt, tool defs, retrieved docs, conversation history, the
user's new message -- AND the space reserved for the reply.

This is an admission-control / allocator problem:
  1. Reserve output space first (input and output share the window).
  2. Place mandatory items (system, tools, new message). If they don't fit,
     that's a hard error.
  3. Fill remaining "flex" budget with history, newest-first.
  4. Evict whatever doesn't fit, lowest priority first.

Pure Python. No dependencies. Run:  python3 budget.py
"""

from dataclasses import dataclass


@dataclass
class Item:
    name: str
    tokens: int
    priority: str  # "mandatory" or "flex"


def pack(window: int, reserved_output: int, mandatory: list, history: list):
    """
    window          : total context window in tokens
    reserved_output : tokens held back for the reply (never used by input)
    mandatory       : items that must be present (system, tools, new message)
    history         : conversation turns, OLDEST-FIRST (we keep newest)

    Returns (included, evicted, report_lines).
    """
    input_budget = window - reserved_output
    report = []
    report.append(f"window            = {window:>6} tokens")
    report.append(f"reserved (output) = {reserved_output:>6} tokens  (protected -- input may never use this)")
    report.append(f"input budget      = {input_budget:>6} tokens  (window - reserved)")
    report.append("")

    # --- Step 1: mandatory items come out of the budget first ---
    mandatory_total = sum(i.tokens for i in mandatory)
    report.append("MANDATORY (always included; error if these alone overflow):")
    for i in mandatory:
        report.append(f"   [keep] {i.name:<22} {i.tokens:>6}")
    report.append(f"   mandatory total       {mandatory_total:>6}")
    report.append("")

    if mandatory_total > input_budget:
        report.append(f"!! HARD ERROR: mandatory {mandatory_total} > input budget {input_budget}.")
        report.append("   Nothing to evict -- you must shrink the system prompt / message itself.")
        return [], history[:], report

    flex_budget = input_budget - mandatory_total
    report.append(f"flex budget       = {flex_budget:>6} tokens  (input budget - mandatory)")
    report.append("")

    # --- Step 2: fill flex budget with history, NEWEST first ---
    report.append("HISTORY (newest-first; keep until the next turn won't fit):")
    included = []
    evicted = []
    remaining = flex_budget
    for turn in reversed(history):  # newest first
        if turn.tokens <= remaining:
            included.append(turn)
            remaining -= turn.tokens
            report.append(f"   [keep] {turn.name:<22} {turn.tokens:>6}   (remaining flex: {remaining})")
        else:
            evicted.append(turn)
            report.append(f"   [DROP] {turn.name:<22} {turn.tokens:>6}   (won't fit in {remaining})")

    included_tokens = mandatory_total + sum(t.tokens for t in included)
    report.append("")
    report.append(f"USED  = {included_tokens} / {input_budget} input tokens "
                  f"({included_tokens * 100 // input_budget}% of input budget)")
    report.append(f"TOTAL = {included_tokens + reserved_output} / {window} window "
                  f"(incl. {reserved_output} reserved for reply)")
    report.append(f"EVICTED {len(evicted)} old turn(s): {[t.name for t in evicted] or 'none'}")

    return [m for m in mandatory] + list(reversed(included)), evicted, report


def scenario(title, window, reserved_output, mandatory, history):
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)
    _, _, report = pack(window, reserved_output, mandatory, history)
    print("\n".join(report))
    print()


if __name__ == "__main__":
    # A small 8K window so the effects are easy to see.
    mandatory = [
        Item("system_prompt", 800, "mandatory"),
        Item("tool_defs", 600, "mandatory"),
        Item("user_new_message", 300, "mandatory"),
    ]
    # Conversation history, oldest-first. 10 turns of ~500 tokens each.
    history = [Item(f"turn_{i:02d}", 500, "flex") for i in range(1, 11)]

    # Scenario A: generous window -- everything fits.
    scenario("A. 8K window, 1K reserved for reply -- most history fits",
             window=8000, reserved_output=1000,
             mandatory=mandatory, history=history)

    # Scenario B: same content, but we reserve MORE for the reply.
    # Less input budget -> more old turns get evicted.
    scenario("B. Same, but reserve 3K for a long reply -- more eviction",
             window=8000, reserved_output=3000,
             mandatory=mandatory, history=history)

    # Scenario C: a big retrieved document shows up as mandatory-ish content.
    # Watch it crowd out history.
    mandatory_with_doc = mandatory + [Item("retrieved_doc", 3500, "mandatory")]
    scenario("C. A 3.5K retrieved doc lands -- it crowds out most history",
             window=8000, reserved_output=1000,
             mandatory=mandatory_with_doc, history=history)

    # Scenario D: mandatory items alone blow the budget -> hard error.
    huge_system = [Item("HUGE_system_prompt", 7500, "mandatory"),
                   Item("user_new_message", 300, "mandatory")]
    scenario("D. Oversized system prompt -- mandatory alone overflows (hard error)",
             window=8000, reserved_output=1000,
             mandatory=huge_system, history=history)
