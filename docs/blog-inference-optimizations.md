# 5 Optimizations That Actually Make LLM Inference Fast

> **The short version:** decode is *memory-bound*, not compute-bound. Every serious LLM
> inference optimization — FlashAttention, PagedAttention, continuous batching, speculative
> decoding, MLA — is the same trade dressed up five different ways: **spend the GPU's idle
> compute to buy back scarce memory bandwidth.** Learn the trade once and the whole field
> becomes readable.
>
> This post is the follow-up to
> [*The 9 Stages of LLM Inference*](./blog-how-llm-inference-works.md). That one walked the
> pipeline; this one explains why each hot stage looks the way it does.

If you haven't read the prerequisite, the vocabulary you'll need — **prefill**, **decode**,
**KV cache**, **block manager**, **scheduler**, **9 stages** — all lives there. I'll keep
referring back to stage numbers from that pipeline.

---

## The one number to hold onto: 295 FLOP/byte

Pick any modern serving GPU — say an H100:

- Compute: **989 TFLOP/s** (FP16 tensor cores)
- HBM bandwidth: **3.35 TB/s**
- **Ridge point** (arithmetic intensity where compute and memory balance):
  989e12 ÷ 3.35e12 ≈ **295 FLOP/byte**.

Anything under 295 FLOP/byte is memory-bound: the tensor cores are done before the next
byte arrives from HBM, so throughput is set by bandwidth, not by TFLOPs.

Now look at a single-token **decode step** on a 70B FP16 model (~140 GB of weights). To
produce one token you read the entire weight set once and do roughly one multiply-add per
weight per token — arithmetic intensity ≈ **1 FLOP/byte**. That's ~300× *below* the ridge
point. Concretely: 140 GB ÷ 3.35 TB/s ≈ **41.8 ms per token → ~24 tok/s**, with the tensor
cores about **99.7 % idle**. You bought an H100 to watch its compute units wait on memory.

That's the memory wall. It's why decode latency is basically a function of `model_size /
HBM_bandwidth`, and it's what every optimization below is fighting.

The five techniques touch different stages of the 9-stage pipeline, but they all obey the
same rule: **if compute is free, use it to save memory traffic.**

---

## 1. FlashAttention — fix the attention kernel

**Stages affected:** 5 (prefill), 6 (decode).

**The problem.** Attention is `softmax(QKᵀ / √d) · V`. Written naively you materialize the
full **N × N** scores matrix in HBM, read it back to compute softmax, read it *again* to
multiply by V. For a 4K context that's ~16M entries per head, per layer — and on something
like Llama 70B (d_model 8192 = 64 heads × 128, ~80 layers) that N×N matrix appears
**~64 × 80 ≈ 5,000 times per forward pass**. HBM traffic explodes; the tensor cores idle.

**The insight.** The N×N matrix is a *transient*. You don't need it — you only need its
softmax-weighted product with V. FlashAttention (Dao et al., 2022) tiles Q, K, V into
blocks small enough to fit in on-chip **SRAM**, and streams them through a single fused
kernel. The trick is **online softmax**: for each new tile, keep a running max `m` and a
running normalizer `ℓ`; when a bigger max shows up, rescale the accumulated output on the
fly. The final result is bit-identical to standard attention — it's the *exact* same math,
just reordered so the N×N matrix is **never written to HBM**.

**The payoff.** Memory traffic drops from O(N²) to O(N). At N = 4K that's roughly a
**1000× reduction** in attention I/O, and 2–4× wall-clock speedup on prefill. This is the
canonical "IO-awareness beats FLOP reduction" result: FlashAttention does *the same number
of FLOPs* as vanilla attention. It only wins because it stopped touching slow memory.

Biggest impact: it lowers **TTFT** (time to first token), because prefill spends a huge
fraction of its time in attention on long prompts.

Same enemy, same trade: spend a bit of extra recompute (rescaling as tiles stream) to save
HBM bandwidth.

---

## 2. PagedAttention — virtual memory for the KV cache

**Stage affected:** 4 (block manager).

**The problem.** The KV cache is the elephant in the pool. For a 70B model with 8 KV heads
× 128 head_dim × 80 layers × 2 (K,V) × 2 bytes ≈ **320 KB per token**. Every concurrent
request has its own KV cache growing one token at a time. Pre-PagedAttention, servers
reserved a **contiguous max-length slab** for each request (e.g. 4K tokens ≈ 1.25 GB).
Actual generations were usually much shorter, so **60–80 % of the slab was wasted** on
internal fragmentation — plus external fragmentation between slabs. Concurrency collapsed.

**The insight.** This is *exactly* the problem OSes solved 60 years ago. vLLM's
**PagedAttention** (Kwon et al., 2023) applies virtual memory to the KV cache:

- KV memory is cut into fixed-size **blocks** (e.g. 16 tokens each) — the *pages*.
- Each request gets a **block table** mapping logical token positions → scattered physical
  blocks — the *page table*.
- Blocks are allocated **on demand** from a global free list.

Every OS-primitive maps cleanly:

| OS concept       | PagedAttention equivalent                    |
|------------------|----------------------------------------------|
| Page             | KV block (16 tokens of K,V for all layers)   |
| Page table       | Per-request block table                      |
| Physical memory  | Global KV pool in HBM                        |
| Page fault       | Pool empty → **preempt** a request           |
| Swap             | Evict to CPU RAM (or recompute)              |
| Shared page + refcount | **Prefix sharing** across requests     |
| Copy-on-write    | Divergence after a shared prefix             |

**The payoff.** Fragmentation drops from ~60–80 % waste to **<4 %**. That directly buys
several× more concurrent requests on the same GPU. And it unlocks two features you
otherwise couldn't cleanly build:

- **Prefix caching.** Two requests with the same system prompt point their block tables at
  the *same* physical blocks, refcounted. First request pays; every subsequent one gets
  that prefix's KV for free — a huge TTFT win for chatbots. Divergence copies the affected
  block (COW), no more.
- **Preemption.** When the pool runs dry, the scheduler evicts a victim's blocks and later
  recomputes (or swaps to CPU). Same idea as a page fault + swap.

PagedAttention is the reason "an inference server is a scheduler wrapped around a fixed
pool of GPU memory, not a request handler." The scheduler needs a *paged* pool to schedule
against.

---

## 3. Continuous batching — the scheduler that keeps the batch full

**Stage affected:** 3 (scheduler).

**The problem.** From the 295-FLOP/byte number, we know a single-token decode reads ~140 GB
of weights per token. If you batch 32 requests together, you *still* read 140 GB — but you
get 32 tokens out of it. **Batching amortizes the weight read.** So the throughput lever is
obvious: keep the batch as full as possible, all the time.

Old-school **static batching** groups N requests, runs them until *all* finish, then starts
the next batch. Two failures:

- **Head-of-line blocking.** New requests wait for the current batch to drain, even if
  most requests finished long ago.
- **Idle slots.** Requests finish at different lengths. The first to hit `<eos>` leaves an
  empty slot for the rest of the batch — you're paying to stream weights into unused
  compute lanes.

**The insight.** Orca (Yu et al., 2022) — the paper behind continuous batching — schedules
**per token-step, not per request**. Every step:

1. Advance all running requests by one token.
2. Anything that hit `<eos>` this step is retired; its KV blocks return to the pool
   *immediately*.
3. Waiting requests are admitted into the freed capacity, up to a per-step **token
   budget** (`max_num_batched_tokens`).

Prefill and decode aren't rigid phases anymore — each step just closes the gap between how
many tokens a request *has* computed and how many it *needs*. New arrivals slot into the
same step as ongoing decodes.

**The payoff.** Throughput goes up **10–20×** vs static batching on realistic workloads,
because the batch stays full and the amortized 140 GB weight-read is always paying off for
the maximum number of tokens.

This is why serving engines are *schedulers*, not request handlers. The whole architecture
exists to keep that weight stream busy every microsecond.

---

## 4. Speculative decoding — verify k tokens for the price of 1

**Stage affected:** 6 (decode loop).

**The problem.** Even with a full batch and paged KV, single-stream latency for one user is
still bounded by "140 GB per token." If you want *one* answer faster, batching doesn't help
— you have exactly one sequence.

**The insight.** Decode is bandwidth-bound. A forward pass on **one** token and a forward
pass on **eight** tokens both stream the same 140 GB of weights; the extra 7-token math is
almost free. So: use a small, cheap **draft model** to propose *k* tokens speculatively,
then have the big **target model** verify all *k* in a **single forward pass**.

Verification is a rejection-sampling scheme (Leviathan et al., 2023):

- Draft proposes token `x_i` with probability `q(x_i)`; target's true probability is
  `p(x_i)`.
- Accept `x_i` with probability `min(1, p(x_i) / q(x_i))`.
- On the first rejection at position *i*, resample that token from the residual
  distribution `(p − q)⁺` (normalized), and **discard** everything after *i*.

The clean part: the draft's `q` **cancels out** in the algebra. The output distribution is
*provably identical* to sampling from the target alone. Not an approximation — the same
distribution. A bad draft only lowers speedup; it never changes quality.

**The payoff.** Typically **2–3× faster** single-stream decoding, sometimes more with a
well-matched draft. Spends abundant compute (a big verification pass) to buy back scarce
bandwidth (fewer target passes per emitted token).

The demo in the companion repo empirically shows the emitted token frequencies match the
target's distribution even when the draft is deliberately bad — proof that the correctness
is structural, not a heuristic.

---

## 5. MLA — shrink the KV cache itself

**Stages affected:** 4 (block manager), 6 (decode).

**The problem.** Continuous batching wants the batch full; PagedAttention wants the pool
packed. Both are ultimately limited by **KV bytes per token**. Standard multi-head
attention (MHA) with 64 heads × 128 head_dim × 80 layers × 2 (K,V) × 2 bytes = ~320 KB per
token, per request. That's the ceiling on concurrency.

The known escape routes trade quality:

- **MQA** (multi-query): share one K,V across all heads. Tiny cache, but quality drops.
- **GQA** (grouped-query): a middle ground with a few KV heads. What Llama uses.

**The insight.** DeepSeek-V2/V3's **Multi-head Latent Attention** (MLA) stores neither full
K,V nor a shared K,V. It stores **one small learned latent vector per token**, and re-
expands it back to full per-head K,V on the fly via a learned **up-projection** at
attention time. The cache holds the latent; the model reconstructs what it needs.

That's the same trade again in a different disguise: spend extra compute (the up-
projection every step) to shrink the memory footprint. Quality stays close to full MHA
because the reconstruction is learned end-to-end.

**The payoff.** Concretely — one 80 GB GPU with a ~60 GB KV pool at 2000-token context:

- MHA (~320 KB/token): ~11 concurrent users.
- MLA (~9 KB/token equivalent): **~366 concurrent users.**

That's roughly **30× more concurrency** on the same silicon — the biggest single-lever
"more users per GPU" win in modern architectures.

For the full story (MLA plus MoE routing, expert parallelism, FP8 training), the
**DeepSeek-V3 technical report** is the capstone read: a real production system that puts
all of this together.

---

## Run it yourself

Every number above is reproducible on a laptop, no GPU, no dependencies — pure Python. The
companion repo
[**`ai-systems-engineering/01-inference-systems`**](https://github.com/sainiteshGit/ai-systems-engineering/tree/main/01-inference-systems)
has one demo per concept:

- `demo_flashattention.py` — tiled attention with online softmax; asserts bit-identical
  output to naive attention while touching O(N) memory instead of O(N²).
- `demo_speculative.py` — draft + target rejection sampling; prints emitted-token
  frequencies vs the target's true distribution and shows they match even with a bad
  draft.
- `demo_mla.py` — MLA vs MHA KV-byte accounting side by side.
- `inference_simulator.py --batch` — the paged block manager and continuous batching from
  the prior post, running live across multiple requests.
- `demo_all_concepts.py` — every one of the above in a single trace.

Clone it and run any file with `python3`. No pip install, no CUDA.

---

## Summary: five stages, one enemy

| Concept                   | Stage(s) it touches         | One-line what-it-does                                                        |
|---------------------------|-----------------------------|------------------------------------------------------------------------------|
| FlashAttention            | 5 prefill, 6 decode         | Tiles Q/K/V through SRAM with online softmax → attention I/O drops O(N²)→O(N). |
| PagedAttention            | 4 block manager             | OS-style virtual memory for the KV cache → <4% waste, unlocks prefix caching and preemption. |
| Continuous batching       | 3 scheduler                 | Per-token-step scheduling → batch always full, weight-read amortized → 10–20× throughput. |
| Speculative decoding      | 6 decode loop               | Small draft proposes k tokens; big target verifies all k in one pass → 2–3× lower latency, provably identical output. |
| MLA (latent attention)    | 4 block manager, 6 decode   | Store one small latent per token, up-project to K,V on the fly → many× more concurrent users. |

Five different stages. One enemy: the memory wall. Every technique here is the same trade
— **use idle compute to save memory bandwidth** — applied at a different place in the
pipeline.

Once you see that pattern, the rest of the field (prefix caching, chunked prefill,
disaggregated prefill/decode, quantization, expert parallelism, FP8 KV cache) reads as
variations on the same theme. The memory wall isn't going away; the interesting engineering
is what you build against it.

---

## References

- **FlashAttention** — *FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness* (Dao et al., 2022): [arXiv:2205.14135](https://arxiv.org/abs/2205.14135)
- **PagedAttention / vLLM** — *Efficient Memory Management for LLM Serving with PagedAttention* (Kwon et al., 2023): [arXiv:2309.06180](https://arxiv.org/abs/2309.06180)
- **Continuous batching / Orca** — *Orca: A Distributed Serving System for Transformer-Based Generative Models* (Yu et al., 2022): [USENIX OSDI '22](https://www.usenix.org/conference/osdi22/presentation/yu)
- **Speculative decoding** — *Fast Inference from Transformers via Speculative Decoding* (Leviathan et al., 2023): [arXiv:2211.17192](https://arxiv.org/abs/2211.17192)
- **MLA** — *DeepSeek-V2* and *DeepSeek-V3 Technical Report*: [DeepSeek-V3](https://arxiv.org/abs/2412.19437)
- **Roofline model** — Williams et al., 2009: [ACM paper](https://dl.acm.org/doi/10.1145/1498765.1498785)
- **Prior post** — [*The 9 Stages of LLM Inference*](./blog-how-llm-inference-works.md)
- **Runnable demos** — [`ai-systems-engineering/01-inference-systems`](https://github.com/sainiteshGit/ai-systems-engineering/tree/main/01-inference-systems)

*Tags: AI, Machine Learning, LLM, Programming, GPU*
