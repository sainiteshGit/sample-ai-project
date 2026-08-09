"""
Module 01 - Inference Systems : ALL CONCEPTS in one runnable file.

Run:            python3 demo_all_concepts.py
Capture output: python3 demo_all_concepts.py > module01_output.txt 2>&1

Pure Python, no dependencies. Covers, in order:
  [A] Roofline recap         - WHY decode is memory-bound (the premise)
  [1] FlashAttention         - identical output, O(N^2)->O(N) HBM traffic
  [2] PagedAttention         - KV in fixed blocks + block table (page table)
  [3] Continuous batching    - per-step admit/advance/evict, batch stays full
  [4] Speculative decoding   - draft/verify, output PROVABLY == target
  [5] MLA (DeepSeek)         - one latent per token -> many more concurrent users

Each section is standalone; edit the knobs at the top of each function to play.
"""
import math
import random


def banner(title):
    print("\n" + "=" * 74)
    print(f"  {title}")
    print("=" * 74)


# =========================================================================== #
# [A] ROOFLINE RECAP  - the premise the whole module rests on
# =========================================================================== #
def demo_roofline():
    banner("[A] ROOFLINE  -  why decode is memory-bound (the premise)")
    PARAMS, BYTES_W = 70e9, 2
    GPU_FLOPS, GPU_BW = 989e12, 3.35e12
    model_bytes = PARAMS * BYTES_W
    ridge = GPU_FLOPS / GPU_BW
    print(f"model 70B FP16 = {model_bytes/1e9:.0f} GB weights | "
          f"H100 {GPU_FLOPS/1e12:.0f} TFLOP/s, {GPU_BW/1e12:.2f} TB/s | "
          f"ridge = {ridge:.0f} FLOP/byte")

    def line(name, tokens):
        flops = 2 * PARAMS * tokens
        ai = flops / model_bytes
        t = max(flops / GPU_FLOPS, model_bytes / GPU_BW)
        bound = "COMPUTE" if flops / GPU_FLOPS > model_bytes / GPU_BW else "MEMORY"
        print(f"  {name:<26} AI={ai:>7.1f}  {bound}-bound  {t*1000:>7.1f} ms/pass")

    line("PREFILL (1000 prompt tok)", 1000)
    line("DECODE (1 token)", 1)
    t_tok = model_bytes / GPU_BW
    print(f"  --> decode ceiling: {model_bytes/1e9:.0f} GB / {GPU_BW/1e12:.2f} TB/s "
          f"= {t_tok*1000:.1f} ms/token = ~{1/t_tok:.0f} tok/s, cores ~99.7% idle")
    print("  EVERY optimization below spends that idle compute to save memory traffic.")


# =========================================================================== #
# [1] FLASHATTENTION  - exact output, far less HBM traffic
# =========================================================================== #
def demo_flashattention():
    banner("[1] FLASHATTENTION  -  same math, O(N^2) -> O(N) HBM traffic")
    N, D, BYTES, TILE = 8, 4, 2, 2
    random.seed(0)
    Q = [[random.uniform(-1, 1) for _ in range(D)] for _ in range(N)]
    K = [[random.uniform(-1, 1) for _ in range(D)] for _ in range(N)]
    V = [[random.uniform(-1, 1) for _ in range(D)] for _ in range(N)]
    dot = lambda a, b: sum(x * y for x, y in zip(a, b))
    scale = 1.0 / math.sqrt(D)

    # naive: materialize N*N scores in HBM (write/read/read)
    hbm_naive = 0
    scores = [[dot(Q[i], K[j]) * scale for j in range(N)] for i in range(N)]
    hbm_naive += N * N * BYTES
    hbm_naive += N * N * BYTES
    W = []
    for i in range(N):
        m = max(scores[i]); e = [math.exp(s - m) for s in scores[i]]; s = sum(e)
        W.append([x / s for x in e])
    hbm_naive += N * N * BYTES + N * N * BYTES
    out_naive = [[sum(W[i][j] * V[j][d] for j in range(N)) for d in range(D)] for i in range(N)]

    # flash: tile + online softmax, never write N*N
    hbm_flash = 4 * (N * D * BYTES)
    out_flash = [[0.0] * D for _ in range(N)]
    for i in range(N):
        m_i, l_i, acc = -float("inf"), 0.0, [0.0] * D
        for jt in range(0, N, TILE):
            for j in range(jt, min(jt + TILE, N)):
                s = dot(Q[i], K[j]) * scale
                m_new = max(m_i, s)
                corr = math.exp(m_i - m_new) if m_i != -float("inf") else 0.0
                p = math.exp(s - m_new)
                l_i = l_i * corr + p
                for d in range(D):
                    acc[d] = acc[d] * corr + p * V[j][d]
                m_i = m_new
        out_flash[i] = [a / l_i for a in acc]

    diff = max(abs(out_naive[i][d] - out_flash[i][d]) for i in range(N) for d in range(D))
    print(f"max |naive - flash| = {diff:.2e}  -> identical (online softmax is exact)")
    print(f"HBM bytes @N={N}:  naive={hbm_naive:,} (O(N^2))   flash={hbm_flash:,} (O(N))")
    print(f"\n{'N':>8}{'naive O(N^2)':>18}{'flash O(N)':>15}{'ratio':>9}")
    for n in [8, 128, 1024, 4096, 16384]:
        nb, fb = 4 * n * n * BYTES, 4 * n * D * BYTES
        print(f"{n:>8}{nb:>18,}{fb:>15,}{nb/fb:>8.0f}x")
    print("  -> at N=4096, ~1000x less attention memory traffic, SAME output")


# =========================================================================== #
# [2]+[3] PAGEDATTENTION + CONTINUOUS BATCHING  - a tiny inference server
# =========================================================================== #
def demo_server():
    banner("[2]+[3] PAGEDATTENTION + CONTINUOUS BATCHING  -  a tiny KV server")
    BLOCK_SIZE, TOTAL_BLOCKS, TOKEN_BUDGET = 4, 8, 8
    cdiv = lambda a, b: -(-a // b)

    class Req:
        def __init__(self, name, prompt_len, gen):
            self.name, self.prompt_len, self.gen = name, prompt_len, gen
            self.computed, self.produced, self.blocks, self.prefilled = 0, 0, [], False

    free = list(range(TOTAL_BLOCKS))          # the free block pool
    def need_blocks(r):                        # grow block table on demand
        want = cdiv(max(r.computed, 1), BLOCK_SIZE)
        while len(r.blocks) < want and free:
            r.blocks.append(free.pop(0))
    def release(r):
        free.extend(r.blocks); r.blocks = []; free.sort()

    waiting = [Req("R1", 6, 5), Req("R2", 2, 4), Req("R3", 5, 3)]
    running = []
    print(f"KV pool: {TOTAL_BLOCKS} blocks x {BLOCK_SIZE} tok = {TOTAL_BLOCKS*BLOCK_SIZE} slots"
          f" | budget/step {TOKEN_BUDGET}")
    for r in waiting:
        print(f"  {r.name}: prompt {r.prompt_len} tok, generate {r.gen}")
    print("-" * 74)

    step = 0
    while waiting or running:
        budget = TOKEN_BUDGET
        ev = []
        # advance running (decode 1 tok each), evict finished -> free KV NOW
        for r in list(running):
            if budget <= 0:
                break
            r.computed += 1; r.produced += 1; budget -= 1
            need_blocks(r)
            if r.produced >= r.gen:
                release(r); running.remove(r)
                ev.append(f"FINISH {r.name} (freed KV)")
        # admit waiting (prefill whole prompt) into leftover budget + KV
        while waiting and budget > 0:
            r = waiting[0]
            if len(free) < cdiv(r.prompt_len, BLOCK_SIZE):
                ev.append(f"PREEMPT-WAIT {r.name} (KV full)")
                break
            r.computed = r.prompt_len; r.prefilled = True; budget -= min(r.prompt_len, budget)
            need_blocks(r); running.append(waiting.pop(0))
            ev.append(f"ADMIT {r.name} (prefill {r.prompt_len}->{len(r.blocks)} blk)")
        used = TOTAL_BLOCKS - len(free)
        run = ",".join(r.name for r in running) or "-"
        print(f"step {step} | run={run:<10} KV={used}/{TOTAL_BLOCKS} | "
              f"{'; '.join(ev) or '(continuous decode)'}")
        step += 1
        if step > 30:
            break
    print(f"-> done in {step} steps; KV pool restored: {len(free)}/{TOTAL_BLOCKS} free")
    print("  slots free the instant a request finishes; new ones splice in mid-flight")


# =========================================================================== #
# [4] SPECULATIVE DECODING  - output provably matches the TARGET
# =========================================================================== #
def demo_speculative():
    banner("[4] SPECULATIVE DECODING  -  output PROVABLY == target (bad draft)")
    VOCAB = ["Paris", "Lyon", "Nice", "Metz"]
    P = {"Paris": 0.70, "Lyon": 0.20, "Nice": 0.07, "Metz": 0.03}   # target (truth)
    Q = {"Paris": 0.40, "Lyon": 0.40, "Nice": 0.10, "Metz": 0.10}   # draft (wrong)

    def sample(dist):
        r, c = random.random(), 0.0
        for t, p in dist.items():
            c += p
            if r < c:
                return t
        return list(dist)[-1]

    def residual(P, Q):
        raw = {t: max(0.0, P[t] - Q[t]) for t in P}
        s = sum(raw.values())
        return dict(P) if s == 0 else {t: v / s for t, v in raw.items()}

    print(f"target p = {P}\ndraft  q = {Q}")
    random.seed(0)
    TRIALS = 200_000
    counts = {t: 0 for t in VOCAB}
    acc = 0
    for _ in range(TRIALS):
        d = sample(Q)
        if random.random() < min(1.0, P[d] / Q[d]):
            counts[d] += 1; acc += 1
        else:
            counts[sample(residual(P, Q))] += 1
    print(f"\n{'token':<8}{'target p':>10}{'draft q':>10}{'emitted':>10}")
    for t in VOCAB:
        print(f"{t:<8}{P[t]:>10.3f}{Q[t]:>10.3f}{counts[t]/TRIALS:>10.3f}")
    print(f"acceptance rate {acc/TRIALS:.1%} (bad draft) -> emitted == TARGET, not draft")
    print("  a bad draft only lowers speedup; it NEVER changes the output distribution")


# =========================================================================== #
# [5] MLA  - shrink the KV cache -> more concurrent users
# =========================================================================== #
def demo_mla():
    banner("[5] MLA (DeepSeek)  -  one latent/token -> many more users")
    LAYERS, HEADS, HEAD_DIM, BYTES = 80, 64, 128, 2
    LATENT, GQA_GROUPS = 512, 8
    KV_POOL_GB, CTX = 60, 2000

    def kv(kind):
        if kind == "MHA":  return 2 * LAYERS * HEADS * HEAD_DIM * BYTES
        if kind == "GQA":  return 2 * LAYERS * GQA_GROUPS * HEAD_DIM * BYTES
        if kind == "MQA":  return 2 * LAYERS * 1 * HEAD_DIM * BYTES
        if kind == "MLA":  return LAYERS * LATENT * BYTES

    full = HEADS * HEAD_DIM
    print(f"store-time compression: {full*2} numbers (64 heads K,V) -> "
          f"{LATENT} latent ({full*2/LATENT:.0f}x), re-expanded at compute time")
    print(f"\n{'variant':<8}{'KV/token':>11}{'vs MHA':>9}{'slots':>13}{'~users':>9}{'quality':>10}")
    print("-" * 60)
    pool, mha = KV_POOL_GB * 1e9, kv("MHA")
    qual = {"MHA": "best", "GQA": "good", "MQA": "worse", "MLA": "~MHA"}
    for k in ["MHA", "GQA", "MQA", "MLA"]:
        b = kv(k); slots = pool / b
        print(f"{k:<8}{b/1024:>9.0f}K{mha/b:>8.0f}x{slots:>13,.0f}{slots/CTX:>9,.0f}{qual[k]:>10}")
    print("  MLA = MQA-like size at ~MHA quality -> several-x more concurrent users")


# =========================================================================== #
if __name__ == "__main__":
    demo_roofline()
    demo_flashattention()
    demo_server()
    demo_speculative()
    demo_mla()
    banner("SUMMARY  -  five stages, one enemy (the memory wall)")
    rows = [
        ("[1] FlashAttention", "attn kernel", "tile via SRAM, no N*N in HBM -> O(N) traffic"),
        ("[2] PagedAttention", "KV memory", "fixed blocks + block table -> <4% waste"),
        ("[3] Continuous batch", "scheduler", "per-step admit/evict -> batch stays full, 10-20x"),
        ("[4] Speculative dec.", "decode loop", "draft+verify -> many tok/read, output exact"),
        ("[5] MLA", "KV size", "one latent/token -> several-x more users"),
    ]
    for name, where, what in rows:
        print(f"  {name:<22}{where:<14}{what}")
