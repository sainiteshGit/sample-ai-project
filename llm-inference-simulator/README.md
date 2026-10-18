# llm-inference-simulator

A single-file, pure-Python simulation of a vLLM-style LLM inference server — traced stage by stage so you can *see* how one prompt becomes streamed tokens.

## Why

- **Learn without a GPU.** Real inference servers (vLLM, TGI, TensorRT-LLM) hide a lot of machinery behind CUDA kernels and RPC layers. This script strips all of that away and models only the *mechanics* of the pipeline — tokenization, scheduling, paged KV allocation, prefill vs. decode, preemption — in code you can read in one sitting.
- **See the tricky parts.** Continuous batching, PagedAttention-style block allocation, and preemption-with-recompute are demonstrated with a step-by-step trace, not diagrams.
- **Zero dependencies.** Just Python 3 and `collections`. Nothing to install.

## The 9 pipeline stages

1. **API server** — accept the request, assign an id.
2. **Tokenizer** — text → token IDs (toy vocab + on-the-fly ids for unknown words).
3. **Scheduler** — admit under a per-step token budget (continuous batching).
4. **Block manager** — paged KV: allocate `cdiv(tokens, BLOCK_SIZE)` blocks from a free pool.
5. **Prefill** — whole prompt in one forward pass; compute-bound; writes K,V for every prompt token.
6. **Decode loop** — one token per step; memory-bound; reads all past KV, appends new KV.
7. **Detokenizer** — new IDs → text pieces, streamed.
8. **Completion** — EOS / max_tokens hit; free KV blocks (or preempt + recompute if the pool saturates).
9. **Response** — assembled text returned.

## Quick start

Requires Python 3. No `pip install` needed.

```bash
# Interactive: type a prompt and watch it flow through all 9 stages
python3 inference_simulator.py

# Multi-request demo: continuous batching across 3 requests
python3 inference_simulator.py --batch
```

### Sample trace (interactive)

Piping a prompt in non-interactively:

```
$ echo 'what is 2+2' | python3 inference_simulator.py
==========================================================================
END-TO-END INFERENCE  —  tracing your prompt through every stage
==========================================================================

--------------------------------------------------------------------------
[2] TOKENIZER  — text -> token IDs (via tokenizer.json vocab+merges)
--------------------------------------------------------------------------
  tokens       : ['what', 'is', '2', '+', '2']
  token IDs    : [1, 2, 7, 8, 7]
  prompt_len   : 5 tokens

--------------------------------------------------------------------------
[4] BLOCK MANAGER + [5] PREFILL  — allocate paged KV, run prompt in one pass
--------------------------------------------------------------------------
  KV blocks needed : cdiv(5 tokens, 4) = 2 blocks
  allocated blocks : [0, 1]   (pool now 2/8 used)

--------------------------------------------------------------------------
[6] DECODE LOOP  — 1 token/step (memory-bound) + [7] DETOKENIZE (stream)
--------------------------------------------------------------------------
  step 1: reload weights -> read KV[0..5] -> emit 'paris'
  step 2: reload weights -> read KV[0..6] -> emit 'because'
  step 3: reload weights -> read KV[0..7] -> emit 'blue'
  step 4: reload weights -> read KV[0..8] -> emit '4'  (KV grew -> new block 2 allocated)
  step 5: reload weights -> read KV[0..9] -> emit 'rayleigh'
  step 6: reload weights -> read KV[0..10] -> emit '<eos>'
```

### Sample trace (batch)

```
$ python3 inference_simulator.py --batch
step   0 | run=R1,R2        wait=-        KV= 3/8 used | ADMIT R1 (prefill 6 prompt-tok -> 2 KV blocks) ; ADMIT R2 (prefill 2 prompt-tok -> 1 KV blocks)
step   1 | run=R1,R2,R3     wait=-        KV= 5/8 used | ADMIT R3 (prefill 5 prompt-tok -> 2 KV blocks)
step   3 | run=R1,R2,R3     wait=-        KV= 7/8 used | (continuous decode)
step   4 | run=R1           wait=-        KV= 3/8 used | FINISH R2 -> "because blue paris" (freed 3 blocks) ; FINISH R3 -> "because blue" (freed 2 blocks)
step   5 | run=-            wait=-        KV= 0/8 used | FINISH R1 -> "because blue paris 4" (freed 3 blocks)
```

> The "model" here is a stub that emits placeholder tokens deterministically — the point is the pipeline *mechanics*, not the answer quality.

## Configuration

The `CONFIG` block at the top of `inference_simulator.py` controls the regime:

- **`BLOCK_SIZE`** (default `4`) — tokens stored per KV block (like a memory page).
- **`TOTAL_BLOCKS`** (default `8`) — size of the KV pool. **Lower this to force preemption.**
- **`TOKEN_BUDGET`** (default `8`) — max tokens the scheduler will process per step (prefill cap + concurrent decode).
- **`MAX_STEPS`** (default `200`) — safety stop.
- **`VERBOSE_KV`** (default `True`) — print per-request KV block ownership each step.

### Forcing a preemption / recompute

To watch the preemption path fire (KV pool exhausted → newest running request evicted, its blocks freed and requeued to be recomputed later), drop `TOTAL_BLOCKS` well below what the batch needs — e.g. set `TOTAL_BLOCKS = 3` and run `python3 inference_simulator.py --batch`. You'll see a `PREEMPT R… (KV OOM -> freed, requeued, will RECOMPUTE)` event in the step log.

## Notes

- **Pure Python 3, zero third-party dependencies.** No numpy, no torch, no network — just `collections` from the stdlib.
- The tokenizer, scheduler, block manager, and decode loop are all in one file (~380 lines) so you can read the entire server in one pass.
