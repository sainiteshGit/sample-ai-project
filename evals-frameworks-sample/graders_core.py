"""
Framework-agnostic grading primitives (the cheap rungs of the ladder).
======================================================================
Pure functions over a Reservation. Both harnesses wrap these so the deterministic
and state-check logic is identical; only the LLM-judge wiring differs per tool.
"""

from agent import Reservation
from cases import Case


def deterministic_check(output: Reservation | None, case: Case) -> tuple[bool, str]:
    """Rung 1-2: exact/typed field assertions + accepted-status set membership."""
    if output is None:
        return False, "no output (agent returned None)"

    if output.status not in case.accepted_status:
        return False, f"status '{output.status}' not in {case.accepted_status}"

    for chk in case.checks:
        field = chk["field"]
        val = getattr(output, field, None)
        if "equals" in chk:
            if val != chk["equals"]:
                return False, f"{field}={val!r} != {chk['equals']!r}"
        elif "min_count" in chk:
            n = len(val) if isinstance(val, list) else 0
            if n < chk["min_count"]:
                return False, f"{field} has {n} items (need >= {chk['min_count']})"
    return True, "all deterministic checks passed"


def state_check(output: Reservation | None, case: Case) -> tuple[bool, str]:
    """Rung 2: does the outcome text contain the required keywords?"""
    if output is None:
        return False, "no output"
    text = output.as_text().lower()
    missing = [kw for kw in case.keywords if kw.lower() not in text]
    if missing:
        return False, f"missing keywords: {missing}"
    return True, "all keywords present"
