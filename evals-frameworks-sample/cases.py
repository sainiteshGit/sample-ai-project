"""
Shared golden set (the DATASET box).
====================================
One list of cases, consumed by BOTH the DeepEval and the Inspect harness so the
only thing that differs between them is FRAMEWORK ERGONOMICS, not the eval.

Ground truth here is a *region*, not a golden string:
  - accepted_status : the set of statuses that count as correct (why `==` dies)
  - keywords        : substrings that must appear in the agent's text (state check)
  - checks          : typed field assertions (the deterministic/oracle grader)
  - rubric          : natural-language assertions for the LLM-as-judge grader
  - type            : "capability" (can it do the thing) vs
                      "regression" (does it still refuse what it must refuse)
"""

from dataclasses import dataclass, field


@dataclass
class Case:
    id: str
    type: str                       # "capability" | "regression"
    request: str
    accepted_status: list[str]
    keywords: list[str] = field(default_factory=list)
    checks: list[dict] = field(default_factory=list)
    rubric: list[str] = field(default_factory=list)


CASES: list[Case] = [
    Case(
        id="book_saturday_dinner",
        type="capability",
        request=(
            "Hi, I'd like a table for 4 this Saturday at 7 PM. "
            "One person is vegetarian and we're celebrating a birthday."
        ),
        accepted_status=["confirmed", "waitlisted"],
        keywords=["vegetarian", "birthday"],
        checks=[
            {"field": "party_size", "equals": 4},
            {"field": "special_requests", "min_count": 1},
        ],
        rubric=[
            "Agent acknowledged the birthday celebration",
            "Agent noted the vegetarian dietary requirement",
            "Agent message is warm and welcoming",
        ],
    ),
    Case(
        id="peak_friday_waitlist",
        type="capability",
        request="We need a table for 6 people this Friday at 8 PM.",
        accepted_status=["waitlisted", "confirmed"],
        keywords=["wait"],
        checks=[{"field": "party_size", "equals": 6}],
        rubric=[
            "Agent communicated that Friday evening is a busy time",
            "If waitlisted, agent provided an estimated wait time",
        ],
    ),
    Case(
        id="wheelchair_gluten_free",
        type="capability",
        request=(
            "I'd like to reserve a table for 2 on Wednesday at 6:30 PM. "
            "My partner uses a wheelchair and I need gluten-free options."
        ),
        accepted_status=["confirmed"],
        keywords=["wheelchair", "gluten"],
        checks=[
            {"field": "party_size", "equals": 2},
            {"field": "special_requests", "min_count": 2},
        ],
        rubric=[
            "Agent confirmed wheelchair-accessible seating",
            "Agent acknowledged the gluten-free dietary need",
        ],
    ),
    Case(
        id="decline_monday",
        type="regression",
        request="Can I get a table for 2 on Monday at 7 PM?",
        accepted_status=["declined"],
        keywords=["closed", "monday"],
        checks=[],
        rubric=[
            "Agent correctly declined because the restaurant is closed on Mondays",
            "Agent suggested an alternative day",
            "Agent was polite, not dismissive",
        ],
    ),
    Case(
        id="decline_large_group",
        type="regression",
        request="I'd like to book for 20 people next Saturday at 7 PM for a company event.",
        accepted_status=["declined", "waitlisted"],
        keywords=["private"],
        checks=[{"field": "party_size", "equals": 20}],
        rubric=[
            "Agent explained the max party size limit",
            "Agent suggested private dining or calling ahead",
            "Agent did not simply confirm a 20-person booking at a regular table",
        ],
    ),
]
