"""
Restaurant Reservation Agent
=============================
Scenario: A customer asks to book a table at a restaurant.
The agent processes the request and returns a structured reservation
with confirmation, time slot, party size, special accommodations, etc.

"""

import os, json, time
from pydantic import BaseModel, Field, field_validator
from openai import AzureOpenAI, OpenAI
from dotenv import load_dotenv

load_dotenv()


# ─── Structured output schema ────────────────────────────────────────────

class Reservation(BaseModel):
    status: str = Field(description="confirmed | waitlisted | declined")
    date: str = Field(default="", description="Reservation date, e.g. 2026-03-20")
    time: str = Field(default="", description="Reservation time, e.g. 7:00 PM")
    party_size: int = Field(description="Number of guests")
    seating: str = Field(default="none", description="indoor | outdoor | bar | private")
    special_requests: list[str] = Field(default_factory=list,
        description="Dietary needs, accessibility, celebrations, etc.")
    estimated_wait_mins: int = Field(default=0,
        description="Wait time if waitlisted, 0 if confirmed")
    agent_message: str = Field(description="Friendly message to the customer")

    @field_validator("special_requests", mode="before")
    @classmethod
    def coerce_special_requests(cls, v):
        if isinstance(v, str):
            return [v] if v.strip() else []
        return v if v is not None else []

    @field_validator("date", "time", "seating", "status", "agent_message", mode="before")
    @classmethod
    def coerce_str(cls, v):
        return v if v is not None else ""


# ─── Agent implementation ─────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a friendly restaurant reservation agent for "The Golden Fork",
an upscale Italian restaurant. You handle booking requests.

Restaurant rules:
- Open Tuesday–Sunday, 5:00 PM – 11:00 PM. Closed Mondays.
- Max party size: 12. Larger groups need private dining (call ahead).
- Peak hours: Friday & Saturday 7–9 PM (likely waitlisted).
- Outdoor seating available April–October only.
- Can accommodate: vegetarian, vegan, gluten-free, nut allergies, wheelchair access.
- Kids menu available for children under 12.

For each request, return a JSON reservation with:
- status: "confirmed" if available, "waitlisted" if peak, "declined" if impossible
- Appropriate date, time, party_size, seating, special_requests
- estimated_wait_mins (only if waitlisted)
- A warm, helpful agent_message to the customer

Always be polite. If you must decline, explain why and suggest alternatives."""


def _get_client():
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")

    if endpoint and api_key:
        return AzureOpenAI(
            azure_endpoint=endpoint, api_key=api_key, api_version="2024-10-21"
        ), deployment

    if endpoint:
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
        )
        return AzureOpenAI(
            azure_endpoint=endpoint,
            azure_ad_token_provider=token_provider,
            api_version="2024-10-21",
        ), deployment

    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        return OpenAI(api_key=openai_key), os.getenv("OPENAI_MODEL", "gpt-4o")
    raise ValueError("Set AZURE_OPENAI_ENDPOINT (+ optional API_KEY) or OPENAI_API_KEY")


def handle_reservation(request: str) -> tuple[Reservation | None, dict]:
    """
    Run the reservation agent on a customer request.

    Returns (Reservation | None, metadata) where metadata contains:
      - transcript: full messages array (Anthropic: "complete record of the trial")
      - latency_ms, n_total_tokens, n_turns
    """
    client, model = _get_client()

    transcript = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": request},
    ]

    start = time.time()
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=transcript,
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        latency_ms = (time.time() - start) * 1000
        raw = resp.choices[0].message.content
        transcript.append({"role": "assistant", "content": raw})

        reservation = Reservation(**json.loads(raw))
        return reservation, {
            "transcript": transcript,
            "latency_ms": latency_ms,
            "time_to_last_token": latency_ms,
            "n_total_tokens": resp.usage.total_tokens if resp.usage else 0,
            "n_turns": 1,
        }
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        transcript.append({"role": "error", "content": str(e)})
        return None, {
            "transcript": transcript,
            "latency_ms": latency_ms,
            "time_to_last_token": latency_ms,
            "n_total_tokens": 0,
            "n_turns": 1,
            "error": str(e),
        }


if __name__ == "__main__":
    r, m = handle_reservation(
        "Hi, I'd like to book a table for 4 this Saturday at 7 PM. "
        "One person is vegetarian and we're celebrating a birthday."
    )
    print(r.model_dump_json(indent=2) if r else m.get("error"))
