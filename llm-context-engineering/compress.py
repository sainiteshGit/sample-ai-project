"""
compress.py -- What comes off the desk when history overflows, and how.

Module 02 - Context Engineering, Lesson 4.

History grows every turn; the budget is fixed. Eventually you must remove
something. Four policies, from dumbest to smartest:

  (a) drop-oldest  : FIFO. keep last N turns. hard forgetting.
  (b) summarize    : replace old turns with a short LLM-made summary. lossy but graceful.
  (c) retrieve     : store all old turns externally; fetch only relevant ones on demand.
  (d) hybrid/pin   : pin must-keeps + keep recent verbatim + summarize middle + retrieve details.

Engineering framing: a memory hierarchy.
  hot   = last few turns verbatim   (L1)
  warm  = rolling summary of middle (RAM)
  cold  = vector store of old turns (disk, retrieve on miss)

This sim can't call a real LLM (offline, pure Python), so "summarize" and
"embedding retrieval" are faked with simple heuristics -- the POINT is the
policy behavior and what information survives, not model quality.

Run:  python3 compress.py
"""

TOKENS_PER_TURN = 500
BUDGET = 3000          # tokens available for history (after mandatory + reserved)

# A fake 20-turn conversation. Turn 2 plants a critical fact the user will
# refer back to at turn 20.
def build_conversation():
    turns = []
    for i in range(1, 21):
        if i == 2:
            text = "user: please remember my account ID is ACC-7788"
        elif i == 20:
            text = "user: what was my account ID again?"
        else:
            text = f"user: message number {i} about various topics"
        turns.append({"idx": i, "text": text, "tokens": TOKENS_PER_TURN})
    return turns


def fits(tokens):
    return "FITS " if tokens <= BUDGET else "OVER!"


def contains_fact(kept_texts):
    return any("ACC-7788" in t for t in kept_texts)


def report(name, kept_texts, extra_cost_note=""):
    tokens = len(kept_texts) * TOKENS_PER_TURN if kept_texts else 0
    # summaries count differently; caller may override by passing token estimate
    return name, kept_texts, tokens


# ---------- (a) drop-oldest ----------
def drop_oldest(turns):
    keep_n = BUDGET // TOKENS_PER_TURN          # how many turns fit
    kept = turns[-keep_n:]
    texts = [t["text"] for t in kept]
    tokens = len(kept) * TOKENS_PER_TURN
    return "drop-oldest", texts, tokens, "free, cache-friendly"


# ---------- (b) summarize ----------
def summarize(turns):
    # Keep the last few verbatim; compress everything older into ONE summary block.
    keep_verbatim = 4
    recent = turns[-keep_verbatim:]
    old = turns[:-keep_verbatim]
    # Fake summary: a naive summarizer that keeps only "topic" lines and DROPS
    # the specific account-ID detail (models routinely lose specifics!).
    summary_text = f"[summary of {len(old)} earlier turns: user discussed various topics]"
    summary_tokens = 500
    texts = [summary_text] + [t["text"] for t in recent]
    tokens = summary_tokens + len(recent) * TOKENS_PER_TURN
    return "summarize", texts, tokens, "costs an extra LLM call; lossy; cache-hostile"


# ---------- (c) retrieve ----------
def retrieve(turns, query):
    # Keep the last few verbatim; the REST live in an external store.
    keep_verbatim = 4
    recent = turns[-keep_verbatim:]
    old = turns[:-keep_verbatim]
    # Fake retriever: pull old turns whose text shares a keyword with the query.
    # Query "account ID" -> matches the turn that mentions account ID.
    q_words = {"account", "id"}
    retrieved = [t for t in old if q_words & set(t["text"].lower().replace("?", "").split())]
    texts = [f"[retrieved] {t['text']}" for t in retrieved] + [t["text"] for t in recent]
    tokens = (len(retrieved) + len(recent)) * TOKENS_PER_TURN
    return "retrieve", texts, tokens, "external store; near-unbounded memory; can miss"


# ---------- (d) hybrid / pin ----------
def hybrid(turns, query):
    # Pin any turn holding a critical fact (detected here by 'ACC-' marker),
    # keep last few verbatim, summarize the rest.
    pinned = [t for t in turns if "ACC-" in t["text"]]
    recent = turns[-3:]
    pinned_idx = {t["idx"] for t in pinned}
    recent_idx = {t["idx"] for t in recent}
    middle = [t for t in turns if t["idx"] not in pinned_idx and t["idx"] not in recent_idx]
    summary_text = f"[summary of {len(middle)} middle turns: various topics]"
    texts = ([f"[PINNED] {t['text']}" for t in pinned]
             + [summary_text]
             + [t["text"] for t in recent])
    tokens = len(pinned) * TOKENS_PER_TURN + 500 + len(recent) * TOKENS_PER_TURN
    return "hybrid/pin", texts, tokens, "pin + recent + summary; nothing critical at FIFO's mercy"


if __name__ == "__main__":
    turns = build_conversation()
    total = len(turns) * TOKENS_PER_TURN
    print("=" * 72)
    print(f"  20-turn conversation = {total} tokens, but history budget = {BUDGET}")
    print(f"  Critical fact 'ACC-7788' was set at TURN 2; user asks for it at TURN 20.")
    print("=" * 72)
    print()

    results = [
        drop_oldest(turns),
        summarize(turns),
        retrieve(turns, "what was my account ID"),
        hybrid(turns, "what was my account ID"),
    ]

    for name, texts, tokens, note in results:
        has = contains_fact(texts)
        print(f"POLICY: {name}")
        print(f"   final history tokens = {tokens:<5} [{fits(tokens)}]   ({note})")
        print(f"   kept {len(texts)} block(s)")
        print(f"   >>> critical fact ACC-7788 still reachable? "
              f"{'YES' if has else 'NO  <-- user gets a wrong/blank answer'}")
        print()

    print("=" * 72)
    print("  TAKEAWAY")
    print("=" * 72)
    print("  drop-oldest : turn 2 fell off long ago -> fact LOST.")
    print("  summarize   : naive summary dropped the specific ID -> fact LOST.")
    print("  retrieve    : fetched exactly the turn with the ID -> fact SURVIVES.")
    print("  hybrid/pin  : critical fact was pinned -> fact SURVIVES, and it fits.")
    print()
    print("  Lesson: 'drop the oldest' is the default and it silently loses")
    print("  early-established facts. Production pins criticals + retrieves details.")
