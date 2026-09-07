"""
judge_validation_demo.py — using a judge is NOT the same as trusting a judge.

We hand-label a small set of Monday-decline replies (the HUMAN truth), run the
GEval judge on the same replies, then compare. The output is a confusion matrix:

    - agreement        : judge matched the human
    - FALSE PASS       : human said FAIL, judge said PASS   (judge too soft)
    - FALSE FAIL       : human said PASS, judge said FAIL   (judge too harsh)

That is how you decide whether a judge's scores can be trusted at all.

Needs Azure or OpenAI in .env (never commit .env).

    python3.12 judge_validation_demo.py
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

REQUEST = "Can I get a table for 2 on Monday at 7 PM?"

RUBRIC = (
    "Grade the restaurant agent's reply. Pass only if ALL hold: "
    "(1) it declined because the restaurant is closed on Monday; "
    "(2) it suggested another day; "
    "(3) the tone is polite, not dismissive. "
    "Do not reward a longer reply. Ignore length."
)

# (reply, human_label)  — human_label True = a human graded this PASS.
# These are OUR ground truth. The judge does NOT see this column.
LABELED = [
    ("We're closed Mondays — I could do Tuesday at 7 PM instead if that works?", True),
    ("So sorry, we're shut on Mondays! Tuesday or Wednesday evening are lovely — shall I check 7 PM?", True),
    ("No. Closed Monday. Try again later.", False),                       # rude, no alt
    ("We are closed on Mondays.", False),                                 # no alternative offered
    ("Sure! Table for 2, Monday 7 PM — see you then!", False),           # WRONG: booked a closed day
    ("Unfortunately Monday won't work as we're closed; would Tuesday 7 PM suit you?", True),
    ("Mondays are closed. You could come another day I guess.", False),   # vague alt, dismissive tone
    ("Apologies, we don't open Mondays. Friday and Saturday fill up fast, but Tuesday 7 PM is open!", True),
]

THRESHOLD = 0.7


def _config():
    endpoint = (os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("OPENAI_BASE_URL") or "").rstrip("/")
    api_key = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    model = os.getenv("AZURE_OPENAI_DEPLOYMENT") or os.getenv("OPENAI_MODEL") or "gpt-4o"
    return endpoint, api_key, model


def _judge_model(endpoint, api_key, model):
    from deepeval.models import GPTModel
    kwargs = {"model": model, "api_key": api_key}
    if endpoint:
        kwargs["base_url"] = endpoint
        os.environ.setdefault("OPENAI_API_KEY", api_key)
        os.environ.setdefault("OPENAI_BASE_URL", endpoint)
    try:
        return GPTModel(**kwargs)
    except TypeError:
        return GPTModel(model=model)


def main() -> None:
    endpoint, api_key, model = _config()
    if not api_key:
        print("Missing AZURE_OPENAI_API_KEY or OPENAI_API_KEY in .env")
        sys.exit(1)

    from deepeval.test_case import LLMTestCase, SingleTurnParams
    from deepeval.metrics import GEval

    judge = GEval(
        name="MondayDecline",
        criteria=RUBRIC,
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        threshold=THRESHOLD,
        model=_judge_model(endpoint, api_key, model),
    )

    print(f"Judge model: {model}   threshold={THRESHOLD}")
    print(f"Validating the judge against {len(LABELED)} human-labeled replies\n")
    print(f"{'#':>2}  {'human':>6}  {'judge':>6}  {'score':>5}  result")

    agree = false_pass = false_fail = 0
    for i, (reply, human_pass) in enumerate(LABELED, 1):
        case = LLMTestCase(input=REQUEST, actual_output=reply)
        judge.measure(case)
        judge_pass = judge.is_successful()
        score = judge.score if judge.score is not None else float("nan")

        if judge_pass == human_pass:
            tag = "ok"
            agree += 1
        elif judge_pass and not human_pass:
            tag = "<< FALSE PASS (judge too soft)"
            false_pass += 1
        else:
            tag = "<< FALSE FAIL (judge too harsh)"
            false_fail += 1

        print(f"{i:>2}  {('PASS' if human_pass else 'FAIL'):>6}  "
              f"{('PASS' if judge_pass else 'FAIL'):>6}  {score:>5.2f}  {tag}")

    n = len(LABELED)
    print("\n--- judge scorecard ---")
    print(f"agreement   : {agree}/{n} = {agree/n:.0%}")
    print(f"false passes: {false_pass}  (judge approved a reply a human failed)")
    print(f"false fails : {false_fail}  (judge rejected a reply a human passed)")
    print("\nA judge you can trust has HIGH agreement and — most importantly —")
    print("near-zero FALSE PASSES. A judge that rubber-stamps bad replies makes")
    print("your whole eval lie in the optimistic direction.")


if __name__ == "__main__":
    main()
