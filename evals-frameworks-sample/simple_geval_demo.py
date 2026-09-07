"""
simple_geval_demo.py — GEval = DeepEval's LLM-as-judge.

Same Monday request. Same fact (closed). Two wordings: polite vs cold.
GEval scores MEANING against a rubric (0-1). Threshold 0.7 = pass.

Needs Azure or OpenAI in .env (never commit .env).

    python3.12 simple_geval_demo.py
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

POLITE = (
    "We're closed on Mondays — I can book you Tuesday at 7 PM instead "
    "if that works?"
)
COLD = "No. Closed Monday. Try again later."


def _config():
    endpoint = (os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("OPENAI_BASE_URL") or "").rstrip("/")
    api_key = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    model = os.getenv("AZURE_OPENAI_DEPLOYMENT") or os.getenv("OPENAI_MODEL") or "gpt-4o"
    return endpoint, api_key, model


def _judge_model(endpoint: str, api_key: str, model: str):
    """GEval needs a DeepEval model. Azure v1 is OpenAI-compatible (base_url)."""
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
        threshold=0.7,
        model=_judge_model(endpoint, api_key, model),
    )

    print("Judge model:", model)
    print("Request    :", REQUEST)
    print("Rubric     : declined Monday + offered another day + polite")
    print("Threshold  : 0.7  (score >= 0.7 => PASS)\n")

    for label, reply in [("polite", POLITE), ("cold", COLD)]:
        case = LLMTestCase(input=REQUEST, actual_output=reply)
        judge.measure(case)
        verdict = "PASS" if judge.is_successful() else "FAIL"
        score = judge.score if judge.score is not None else float("nan")
        print(f"{label:6}  score={score:.2f}  {verdict}")
        print(f"        {reply}")
        print(f"        reason: {judge.reason}\n")


if __name__ == "__main__":
    main()
