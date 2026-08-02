#!/usr/bin/env python3
"""
inference_simulator.py  —  end-to-end LLM inference server, simulated.

A single, runnable, pure-Python model of everything a vLLM-style inference server
does to turn an HTTP prompt into streamed tokens. No numpy, no GPU, no network —
just the mechanics, traced one scheduler step at a time so you can SEE them.

Pipeline stages modelled (same numbering as the module-01 end-to-end):

  [1] API server        accept request, assign id
  [2] Tokenizer         text -> token IDs        (toy byte/word vocab + merges)
  [3] Scheduler         per-step admission under a token budget (continuous batching)
  [4] Block manager     paged KV: cdiv(tokens, block_size) blocks from a free pool
  [5] Prefill           whole prompt in one pass -> writes KV for every prompt token
  [6] Decode loop       1 token/step, memory-bound; reads all past KV, appends new KV
  [7] Detokenizer       new IDs -> text pieces, streamed
  [8] Completion        EOS / max_tokens -> free KV blocks (slot reused)
  [9] Response          assembled text returned

It also demonstrates the three things that make serving hard:
  * continuous batching   (requests join/leave the running set mid-flight)
  * PagedAttention        (KV stored in fixed blocks, allocated on demand)
  * preemption -> recompute (V1 behaviour when the KV pool is exhausted)

Run:
    python3 inference_simulator.py
Tweak the CONFIG block to make preemption fire, change the batch, etc.
"""

import collections

# ----------------------------------------------------------------------------
# CONFIG  — change these to explore different regimes
# ----------------------------------------------------------------------------
BLOCK_SIZE       = 4     # tokens stored per KV block (like a page)
TOTAL_BLOCKS     = 8     # size of the KV pool. LOWER this to force preemption.
TOKEN_BUDGET     = 8     # max tokens the scheduler will process per step (prefill cap)
MAX_STEPS        = 200   # safety stop
VERBOSE_KV       = True  # print per-request KV block ownership each step


def cdiv(a, b):
    return (a + b - 1) // b


# ============================================================================
# [2] TOKENIZER  — a toy but real tokenizer: fixed vocab + greedy merges.
#     Mirrors what tokenizer.json encodes (vocab + merge rules), just tiny.
# ============================================================================
class ToyTokenizer:
    def __init__(self):
        # a minimal vocab; real models have 50k-256k entries in tokenizer.json
        words = ["<eos>", "what", "is", "the", "capital", "of", "france",
                 "2", "+", "why", "sky", "blue", "paris", "4", "because",
                 "rayleigh", "scattering", "?", " "]
        self.stoi = {w: i for i, w in enumerate(words)}
        self.itos = {i: w for w, i in self.stoi.items()}
        self.EOS = self.stoi["<eos>"]
        self.next_id = len(self.stoi)

    def encode(self, text):
        # split into word tokens; unknown words get a fresh, stable id (like BPE
        # would map unseen text to sub-word ids). This lets ANY typed prompt work.
        ids = []
        for tok in text.lower().replace("?", " ?").replace("+", " + ").split():
            if tok not in self.stoi:
                self.stoi[tok] = self.next_id
                self.itos[self.next_id] = tok
                self.next_id += 1
            ids.append(self.stoi[tok])
        return ids

    def decode_piece(self, tid):
        return self.itos.get(tid, "<unk>")


# ============================================================================
# [4] BLOCK MANAGER  — the paged KV allocator.
#     Free blocks live in a queue. A request grows its block list as it produces
#     tokens; blocks are returned to the pool when it finishes or is preempted.
# ============================================================================
class BlockManager:
    def __init__(self, n_blocks):
        self.free = collections.deque(range(n_blocks))
        self.total = n_blocks

    def free_count(self):
        return len(self.free)

    def used(self):
        return self.total - len(self.free)

    def ensure(self, req):
        """Grow req.blocks to cover req.computed tokens. False if the pool is empty."""
        need = cdiv(req.computed, BLOCK_SIZE) - len(req.blocks)
        if need <= 0:
            return True
        if need > len(self.free):
            return False
        for _ in range(need):
            req.blocks.append(self.free.popleft())
        return True

    def release(self, req):
        for b in req.blocks:
            self.free.append(b)
        req.blocks = []


# ============================================================================
# REQUEST  — one in-flight generation. Tracks how far it has been computed and
#            which KV blocks it owns.
# ============================================================================
class Request:
    def __init__(self, rid, prompt_text, gen_len, arrival, tok):
        self.rid = rid
        self.prompt_text = prompt_text
        self.prompt_ids = tok.encode(prompt_text)       # [2] tokenize up front
        self.prompt_len = len(self.prompt_ids)
        self.gen_len = gen_len                           # tokens to generate
        self.total = self.prompt_len + gen_len
        self.arrival = arrival
        self.computed = 0                                # tokens processed so far
        self.blocks = []                                 # owned KV blocks
        self.out_ids = []                                # generated token ids
        self.state = "waiting"                           # waiting|running|done
        self.prefilled = False

    def remaining(self):
        return self.total - self.computed


# ============================================================================
# [1][3][5][6][7][8][9]  THE SERVER LOOP
# ============================================================================
class InferenceServer:
    def __init__(self, requests):
        self.tok = ToyTokenizer()
        self.bm = BlockManager(TOTAL_BLOCKS)
        self.incoming = requests
        self.waiting = collections.deque()
        self.running = []
        self.finished = []
        self.step = 0

    # ---- a fake "model": pick a plausible next token id deterministically ----
    def _next_token(self, req):
        # not a real model — just produces a deterministic stream so the trace is stable
        if len(req.out_ids) >= req.gen_len - 1:
            return self.tok.EOS
        pool = [self.tok.stoi[w] for w in ("paris", "4", "because", "blue")]
        return pool[(len(req.out_ids) + len(req.rid)) % len(pool)]

    def _admit_arrivals(self):
        # [1] API server: newly-arrived requests enter the waiting queue
        for r in self.incoming:
            if r.arrival == self.step:
                r.state = "waiting"
                self.waiting.append(r)

    def _advance_running(self, budget, events):
        # [6] DECODE: each running request produces one token this step
        for r in list(self.running):
            if budget <= 0:
                break
            r.computed += 1
            budget -= 1
            if not self.bm.ensure(r):
                # [4] KV pool exhausted -> [preempt] newest running request (FCFS)
                victim = self.running.pop()
                victim.computed = 0
                victim.out_ids = []
                victim.prefilled = False
                self.bm.release(victim)
                victim.state = "waiting"
                self.waiting.appendleft(victim)
                events.append("PREEMPT %s (KV OOM -> freed, requeued, will RECOMPUTE)" % victim.rid)
                r.computed -= 1
                budget += 1
                continue
            # produce the decode token + detokenize [7]
            tid = self._next_token(r)
            r.out_ids.append(tid)
            if tid == self.tok.EOS or r.computed >= r.total:
                # [8] COMPLETION: free KV, slot reused
                r.state = "done"
                self.running.remove(r)
                self.bm.release(r)
                self.finished.append(r)
                text = " ".join(self.tok.decode_piece(t) for t in r.out_ids if t != self.tok.EOS)
                events.append("FINISH %s -> \"%s\" (freed %d blocks)"
                              % (r.rid, text.strip(), cdiv(r.total, BLOCK_SIZE)))
        return budget

    def _admit_waiting(self, budget, events):
        # [3] SCHEDULER + [5] PREFILL: pull from waiting queue while budget/KV allow
        while self.waiting and budget > 0:
            r = self.waiting[0]
            # prefill cost = whole prompt on first touch, else 1 (a decode-style step)
            chunk = min(r.prompt_len if not r.prefilled else 1, budget)
            r.computed += chunk
            if not self.bm.ensure(r):
                r.computed -= chunk           # KV won't fit -> leave it queued
                break
            self.waiting.popleft()
            r.prefilled = True
            r.state = "running"
            self.running.append(r)
            budget -= chunk
            events.append("ADMIT %s (prefill %d prompt-tok -> %d KV blocks)"
                          % (r.rid, chunk, len(r.blocks)))
        return budget

    def _print_step(self, events):
        run = ",".join(r.rid for r in self.running) or "-"
        wait = ",".join(r.rid for r in self.waiting) or "-"
        line = ("step %3d | run=%-12s wait=%-8s KV=%2d/%d used | %s"
                % (self.step, run, wait, self.bm.used(), TOTAL_BLOCKS,
                   " ; ".join(events) or "(continuous decode)"))
        print(line)
        if VERBOSE_KV:
            for r in self.running:
                print("          %s KV blocks=%s  computed=%d/%d  out=%s"
                      % (r.rid, r.blocks, r.computed, r.total,
                         [self.tok.decode_piece(t) for t in r.out_ids]))

    def run(self):
        print("=" * 78)
        print("INFERENCE SERVER SIMULATION")
        print("KV pool: %d blocks x %d tokens = %d token slots | token budget/step: %d"
              % (TOTAL_BLOCKS, BLOCK_SIZE, TOTAL_BLOCKS * BLOCK_SIZE, TOKEN_BUDGET))
        print("=" * 78)
        # [2] show tokenization of each prompt once, up front
        for r in self.incoming:
            print("  %s prompt=%-28s ids=%s  (gen up to %d)"
                  % (r.rid, '"' + r.prompt_text + '"', r.prompt_ids, r.gen_len))
        print("-" * 78)

        while len(self.finished) < len(self.incoming) and self.step < MAX_STEPS:
            self._admit_arrivals()
            events = []
            budget = TOKEN_BUDGET
            budget = self._advance_running(budget, events)   # [6] decode running
            budget = self._admit_waiting(budget, events)      # [3][5] admit+prefill
            self._print_step(events)
            self.step += 1

        print("-" * 78)
        print("DONE: %d requests in %d steps. KV pool restored: %d/%d free."
              % (len(self.finished), self.step,
                 self.bm.free_count(), TOTAL_BLOCKS))
        print("=" * 78)
        # [9] final responses
        print("RESPONSES:")
        for r in self.finished:
            text = " ".join(self.tok.decode_piece(t) for t in r.out_ids if t != self.tok.EOS)
            print("  %s: %s" % (r.rid, text.strip()))


# ============================================================================
# INTERACTIVE: trace ONE user-typed prompt through every stage, start to end.
# ============================================================================
def serve_one(prompt, max_tokens=6):
    tok = ToyTokenizer()
    bm = BlockManager(TOTAL_BLOCKS)

    def hr(title):
        print("\n" + "-" * 74)
        print(title)
        print("-" * 74)

    print("=" * 74)
    print("END-TO-END INFERENCE  —  tracing your prompt through every stage")
    print("=" * 74)

    # [1] API server -------------------------------------------------------
    hr("[1] API SERVER  — request received")
    req = Request("REQ", prompt, max_tokens, 0, tok)
    print('  raw text     : "%s"' % prompt)
    print("  request_id   : %s" % req.rid)
    print("  max_tokens   : %d" % max_tokens)

    # [2] Tokenizer --------------------------------------------------------
    hr("[2] TOKENIZER  — text -> token IDs (via tokenizer.json vocab+merges)")
    print("  tokens       : %s" % [tok.decode_piece(i) for i in req.prompt_ids])
    print("  token IDs    : %s" % req.prompt_ids)
    print("  prompt_len   : %d tokens" % req.prompt_len)

    # [3] Scheduler --------------------------------------------------------
    hr("[3] SCHEDULER  — admit under token budget (continuous batching)")
    print("  token_budget : %d tokens/step" % TOKEN_BUDGET)
    print("  prompt fits in budget? %s (%d <= %d)"
          % (req.prompt_len <= TOKEN_BUDGET, req.prompt_len, TOKEN_BUDGET))

    # [4] Block manager + [5] Prefill -------------------------------------
    hr("[4] BLOCK MANAGER + [5] PREFILL  — allocate paged KV, run prompt in one pass")
    req.computed = req.prompt_len
    need = cdiv(req.computed, BLOCK_SIZE)
    bm.ensure(req)
    req.prefilled = True
    print("  KV blocks needed : cdiv(%d tokens, %d) = %d blocks"
          % (req.prompt_len, BLOCK_SIZE, need))
    print("  allocated blocks : %s   (pool now %d/%d used)"
          % (req.blocks, bm.used(), TOTAL_BLOCKS))
    print("  prefill: all %d prompt tokens processed in ONE forward pass" % req.prompt_len)
    print("           -> K,V written for every prompt token (compute-bound stage)")

    # [6] Decode loop + [7] Detokenize ------------------------------------
    hr("[6] DECODE LOOP  — 1 token/step (memory-bound) + [7] DETOKENIZE (stream)")
    pool = ["paris", "because", "blue", "4", "rayleigh", "scattering"]
    for step in range(max_tokens):
        req.computed += 1
        before = len(req.blocks)
        bm.ensure(req)
        if step == max_tokens - 1:
            tid = tok.EOS
        else:
            word = pool[step % len(pool)]
            if word not in tok.stoi:
                tok.stoi[word] = tok.next_id
                tok.itos[tok.next_id] = word
                tok.next_id += 1
            tid = tok.stoi[word]
        req.out_ids.append(tid)
        note = ""
        if len(req.blocks) > before:
            note = "  (KV grew -> new block %d allocated)" % req.blocks[-1]
        stream = "<eos>" if tid == tok.EOS else tok.decode_piece(tid)
        print("  step %d: reload weights -> read KV[0..%d] -> emit '%s'%s"
              % (step + 1, req.computed - 1, stream, note))
        if tid == tok.EOS:
            break

    # [8] Completion -------------------------------------------------------
    hr("[8] COMPLETION  — EOS/max_tokens hit, free KV blocks (slot reused)")
    freed = len(req.blocks)
    bm.release(req)
    print("  freed %d KV blocks back to pool  (pool now %d/%d used)"
          % (freed, bm.used(), TOTAL_BLOCKS))

    # [9] Response ---------------------------------------------------------
    hr("[9] RESPONSE  — assembled text returned to caller")
    text = " ".join(tok.decode_piece(t) for t in req.out_ids if t != tok.EOS)
    print('  generated ids : %s' % req.out_ids)
    print('  response text : "%s"' % text.strip())
    print("=" * 74)
    print("(Note: the 'model' here is a stub — it emits placeholder tokens. The point")
    print(" is the PIPELINE mechanics, not the answer. Real serving = same stages.)")


# ============================================================================
# WORKLOAD  — three requests; R3 arrives late and triggers memory pressure.
# ============================================================================
def build_workload(tok):
    return [
        #        id    prompt                         gen  arrival
        Request("R1", "what is the capital of france", 5, 0, tok),
        Request("R2", "why is the sky blue",           4, 0, tok),
        Request("R3", "what is 2 + 2",                  3, 1, tok),
    ]


if __name__ == "__main__":
    import sys
    if "--batch" in sys.argv:
        # multi-request scheduler demo (continuous batching + preemption)
        tok = ToyTokenizer()
        InferenceServer(build_workload(tok)).run()
    else:
        # interactive end-to-end: start from YOUR input
        try:
            prompt = input("Enter your prompt: ").strip()
        except EOFError:
            prompt = ""
        if not prompt:
            prompt = "what is the capital of france"
            print("(no input given, using default: \"%s\")" % prompt)
        serve_one(prompt, max_tokens=6)

