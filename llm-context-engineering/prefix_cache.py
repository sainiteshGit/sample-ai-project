"""
prefix_cache.py -- Why prompt LAYOUT decides your bill.

Module 02 - Context Engineering, Lesson 3.

A transformer's KV vectors are causal: a token's K/V depends only on itself and
the tokens BEFORE it. So the KV of a prefix is a pure function of that prefix.
=> Compute a prefix's KV once, cache it, reuse it for any request that starts
   with the same tokens.

The catch: it's a PREFIX cache. It matches left-to-right and stops at the FIRST
differing token. One volatile token near the FRONT (a timestamp!) invalidates
everything after it.

Rule: stable content first, volatile content last.

This sim models each request as a list of "blocks" (chunks of tokens). It caches
blocks by the hash of everything up to and including them (the prefix identity),
then measures the cached-prefix length request-over-request.

Pure Python. No dependencies. Run:  python3 prefix_cache.py
"""

import hashlib

# Pricing knobs (illustrative, roughly matching real APIs)
PRICE_PER_UNCACHED = 3.00 / 1_000_000   # $ per input token, full price
PRICE_PER_CACHED   = 0.30 / 1_000_000   # $ per input token, cached (10x cheaper)


def block_hash(prefix_ids):
    """Identity of a prefix = hash of the whole token sequence up to here."""
    return hashlib.sha256(repr(prefix_ids).encode()).hexdigest()[:8]


class PrefixCache:
    def __init__(self):
        self.seen = set()  # set of prefix-hashes we've already computed KV for

    def process(self, blocks):
        """
        blocks: list of (name, token_ids). We walk left-to-right, building the
        cumulative prefix. A block is a CACHE HIT if the cumulative prefix hash
        up to and including it was already seen. The first miss breaks the chain
        (everything after must be recomputed, because its prefix now differs).
        """
        cumulative = []
        cached_tokens = 0
        computed_tokens = 0
        still_hitting = True
        trace = []

        for name, ids in blocks:
            cumulative += ids
            h = block_hash(cumulative)
            if still_hitting and h in self.seen:
                cached_tokens += len(ids)
                trace.append(f"   [HIT ] {name:<26} {len(ids):>5} tok  (cached)")
            else:
                still_hitting = False
                computed_tokens += len(ids)
                self.seen.add(h)
                trace.append(f"   [miss] {name:<26} {len(ids):>5} tok  (recompute)")
            # Even on a hit we must register the hash so future longer prefixes match.
            self.seen.add(h)

        return cached_tokens, computed_tokens, trace


def cost(cached, computed):
    return cached * PRICE_PER_CACHED + computed * PRICE_PER_UNCACHED


def run_layout(title, make_blocks, turns):
    print("=" * 72)
    print(f"  {title}")
    print("=" * 72)
    cache = PrefixCache()
    total_cached = total_computed = 0
    for t in range(1, turns + 1):
        blocks = make_blocks(t)
        cached, computed, trace = cache.process(blocks)
        total_cached += cached
        total_computed += computed
        hitrate = cached * 100 // (cached + computed)
        print(f"Turn {t:>2}:  cached={cached:>5}  recompute={computed:>5}  "
              f"prefix-hit={hitrate:>3}%   turn cost=${cost(cached, computed):.6f}")
    print("-" * 72)
    total = total_cached + total_computed
    print(f"TOTALS:  cached={total_cached}  recompute={total_computed}  "
          f"overall prefix-hit={total_cached * 100 // total}%")
    print(f"TOTAL COST over {turns} turns = ${cost(total_cached, total_computed):.6f}")
    print()
    return cost(total_cached, total_computed)


# --- Content blocks (token counts are illustrative) ---
SYSTEM = ("system_prompt", list(range(1000, 1000 + 2000)))     # 2000 stable tokens
def history_block(t):
    # Each past turn is a stable, unchanging block once it happened.
    return (f"history_turn_{t:02d}", list(range(9000 + t * 1000, 9000 + t * 1000 + 500)))
def new_msg(t):
    return (f"new_user_msg_{t:02d}", list(range(50000 + t * 100, 50000 + t * 100 + 300)))
def timestamp(t):
    # A volatile block: different every single request.
    return (f"timestamp_{t:02d}", [700000 + t])  # 1 token, but it CHANGES each turn


def volatile_first(t):
    """BAD layout: timestamp on TOP, before the stable system prompt."""
    blocks = [timestamp(t), SYSTEM]
    for past in range(1, t):
        blocks.append(history_block(past))
    blocks.append(new_msg(t))
    return blocks


def stable_first(t):
    """GOOD layout: stable system prompt first, volatile timestamp at the BOTTOM."""
    blocks = [SYSTEM]
    for past in range(1, t):
        blocks.append(history_block(past))
    blocks.append(timestamp(t))   # volatile, but at the end -> only it + new msg miss
    blocks.append(new_msg(t))
    return blocks


if __name__ == "__main__":
    TURNS = 8
    c_bad = run_layout("BAD: timestamp on TOP (volatile-first) -- cache keeps breaking",
                       volatile_first, TURNS)
    c_good = run_layout("GOOD: timestamp on BOTTOM (stable-first) -- prefix stays cached",
                        stable_first, TURNS)

    print("=" * 72)
    print("  VERDICT")
    print("=" * 72)
    print(f"volatile-first total cost : ${c_bad:.6f}")
    print(f"stable-first  total cost  : ${c_good:.6f}")
    if c_good > 0:
        print(f"stable-first is {c_bad / c_good:.1f}x cheaper -- SAME tokens, just reordered.")
