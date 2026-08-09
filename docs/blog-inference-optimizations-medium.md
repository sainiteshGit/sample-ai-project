# 5 Optimizations That Actually Make LLM Inference Fast

You send a prompt to an LLM and tokens stream back. In between is a real distributed-
systems pipeline, and every serious optimization in it is fighting the same fight. This is
the follow-up to [*The 9 Stages of LLM Inference*](./blog-how-llm-inference-works.md); the
vocabulary — prefill, decode, KV cache, block manager, scheduler — lives there.

**The one idea to hold onto:** decode is *memory-bound*, not compute-bound. Every
optimization here spends idle compute to buy back scarce memory bandwidth.

## The number: 295 FLOP/byte

An H100 does 989 TFLOP/s over 3.35 TB/s of HBM. Ridge point ≈ **295 FLOP/byte** — below
that, the tensor cores wait on memory. A single-token decode on a 70B FP16 model streams
~140 GB of weights and does about one multiply-add per weight → intensity ≈ 1 FLOP/byte,
~300× *below* the ridge. Concretely: 140 GB ÷ 3.35 TB/s ≈ **41.8 ms per token → ~24 tok/s**,
tensor cores ~99.7 % idle. That's the memory wall, and it's what everything below fights.

## 1. FlashAttention — fix the attention kernel

**Stages 5 (prefill), 6 (decode).** Naive attention writes the N×N score matrix to HBM,
reads it for softmax, reads it again for `×V`. On Llama-70B (64 heads, 80 layers) that
happens ~5,000 times per forward pass. FlashAttention (Dao 2022) tiles Q/K/V through
on-chip **SRAM** and uses **online softmax** (running max + running sum, rescaling as
tiles stream), so the N×N matrix is **never materialized**. Same FLOPs, bit-identical
output — but attention I/O drops from **O(N²) to O(N)** (~1000× less at N=4K). IO-awareness
beats FLOP reduction. Biggest hit: **TTFT**.

## 2. PagedAttention — virtual memory for the KV cache

**Stage 4.** KV cache on a 70B model ≈ **320 KB per token**, per request. Old servers
reserved a contiguous max-length slab per request → **60–80 % waste** from fragmentation.
vLLM's PagedAttention (Kwon 2023) borrows straight from an OS:

- Page → fixed-size **KV block** (e.g. 16 tokens).
- Page table → per-request **block table**.
- Shared page + refcount → **prefix caching** (identical prompts point at the same
  physical blocks; copy-on-write on divergence).
- Page fault + swap → **preemption** (evict a victim's blocks, recompute or swap to CPU).

Waste drops to **<4 %**, and prefix caching + preemption fall out of the same mechanism.
This is why an inference server is really *a scheduler wrapped around a fixed pool of GPU
memory*.

## 3. Continuous batching — keep the batch full

**Stage 3.** Batching amortizes the 140 GB weight-read across many requests. Static
batching runs a fixed batch to completion — early finishers leave dead slots, new arrivals
wait behind head-of-line. **Continuous batching** (Orca 2022) schedules **per token-step**:
every step advance all running requests one token, retire anything that hit `<eos>` (KV
returns to the pool instantly), admit waiting requests into the freed slots under a token
budget. Batch stays full → **10–20× throughput** on realistic workloads. Prefill and decode
stop being rigid phases; each step just closes the gap between tokens computed and tokens
needed.

## 4. Speculative decoding — verify k tokens for the price of 1

**Stage 6.** Batching doesn't help a *single* user's latency. But because decode is
bandwidth-bound, a target forward pass over 1 token and over 8 tokens both stream the same
140 GB of weights — verifying 8 costs roughly the same as generating 1. Use a small
**draft** model to propose *k* tokens; the big **target** verifies all *k* in one pass, via
rejection sampling: accept `x_i` with probability `min(1, p_target(x_i) / q_draft(x_i))`;
on first rejection, resample from the residual `(p − q)⁺` normalized, discard the rest.

The draft's `q` **cancels out** in the algebra — output distribution is *provably identical*
to sampling the target alone. A bad draft only slows you down, never distorts output.
Typical **2–3× lower latency**. Same trade: burn abundant compute to buy back bandwidth.

## 5. MLA — shrink the KV cache itself

**Stages 4 & 6.** Concurrency is capped by **KV bytes per token**. MHA stores full per-head
K,V (~320 KB/token on a 70B). MQA shares one K,V (small, but quality drops); GQA is the
middle path Llama uses. DeepSeek's **Multi-head Latent Attention** stores **one small
learned latent** per token and **re-expands** it to per-head K,V on the fly via a learned
up-projection. MQA-like size at ~MHA quality.

Concretely, one 80 GB GPU with ~60 GB KV pool at 2000-token context: MHA ≈ **11
concurrent users**, MLA ≈ **366 users** — roughly **30× more concurrency** on the same
silicon. Trade a little compute for scarce memory — the right trade because decode is
memory-bound. DeepSeek-V3's tech report is the capstone real-production read (MLA + MoE +
FP8).

## Five stages, one enemy

| Concept              | Pipeline stage           | What it does                                                     |
|----------------------|--------------------------|------------------------------------------------------------------|
| FlashAttention       | 5 prefill, 6 decode      | Tile Q/K/V through SRAM with online softmax → O(N²)→O(N) attn I/O. |
| PagedAttention       | 4 block manager          | Virtual memory for KV cache → <4 % waste, unlocks prefix caching. |
| Continuous batching  | 3 scheduler              | Per-token-step scheduling → batch stays full → 10–20× throughput. |
| Speculative decoding | 6 decode loop            | Draft proposes k, target verifies in one pass → 2–3× faster, identical output. |
| MLA                  | 4 block mgr, 6 decode    | Store a latent per token, up-project on the fly → many× users.    |

Five different stages. One enemy: the memory wall. Every technique is the same trade —
**spend idle compute, save memory bandwidth** — at a different point in the pipeline.

## Run it yourself

Every number is reproducible on a laptop — no GPU, no deps, pure Python — in
[**`ai-systems-engineering/01-inference-systems`**](https://github.com/sainiteshGit/ai-systems-engineering/tree/main/01-inference-systems):
`demo_flashattention.py`, `demo_speculative.py`, `demo_mla.py`, `demo_all_concepts.py`, and
`inference_simulator.py --batch` for paged KV + continuous batching live.

## References

- **FlashAttention** — Dao et al., 2022: [arXiv:2205.14135](https://arxiv.org/abs/2205.14135)
- **PagedAttention / vLLM** — Kwon et al., 2023: [arXiv:2309.06180](https://arxiv.org/abs/2309.06180)
- **Orca (continuous batching)** — Yu et al., 2022: [OSDI '22](https://www.usenix.org/conference/osdi22/presentation/yu)
- **Speculative decoding** — Leviathan et al., 2023: [arXiv:2211.17192](https://arxiv.org/abs/2211.17192)
- **DeepSeek-V3 (MLA)** — [arXiv:2412.19437](https://arxiv.org/abs/2412.19437)
- **Prior post** — [*The 9 Stages of LLM Inference*](./blog-how-llm-inference-works.md)

*Tags: AI, Machine Learning, LLM, Programming, GPU*
