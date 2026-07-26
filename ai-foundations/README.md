# AI Foundations

A small .NET console project that makes **one call to an AI model completely
transparent**.

It runs nine experiments. Each one asks a single question, sends real requests,
prints the real numbers, and explains what they mean. Nothing is simulated and
nothing is hidden behind a library.

You do not need any AI background to read this. Every term is explained the
first time it appears.

---

## Why this project exists

Most tutorials show you how to *use* an AI model. You install a library, call
`.GetResponseAsync()`, and something comes back. That works right up until
something goes wrong — and then you have no idea why, because a library sits
between you and the thing you are trying to understand.

This project removes the library.

It talks to the model with a plain `HttpClient` and a JSON POST, which is all
any AI library ultimately does. Once you have seen the unwrapped version, every
framework you meet later (Microsoft Agent Framework, Semantic Kernel, LangChain,
OpenAI SDKs) becomes much easier to reason about, because you know what they are
wrapping.

**The goal is not to build a product.** The goal is that afterwards you can
answer the nine questions below from memory.

---

## Vocabulary you need first

Read this once. Everything else assumes these seven terms.

| Term | Plain meaning |
|---|---|
| **Token** | A chunk of text the model actually reads. Roughly 3–4 characters of English. Not a word, not a letter. You are billed per token. |
| **Prompt / input tokens** | Everything you send. |
| **Completion / output tokens** | Everything the model generates back. |
| **Prefill** | The model reading your entire prompt. Happens once, all at once. |
| **Decode** | The model writing the reply, one token at a time. |
| **TTFT** | *Time To First Token*. How long until the first piece of the answer appears. |
| **TPOT** | *Time Per Output Token*. How long each following token takes. |

The one sentence that explains most of this project:

> **Reading your prompt (prefill) and writing the reply (decode) are two
> completely different kinds of work, with two completely different bottlenecks.**

Everything from pricing to latency to why your request is processed alongside
strangers' requests follows from that.

---

## Running it

You need [.NET 8 or newer](https://dotnet.microsoft.com/download) and access to
an Azure OpenAI (or compatible) endpoint.

```bash
cp appsettings.Development.json.template appsettings.Development.json
```

Then open `appsettings.Development.json` and fill in the three values under the
`AzureOpenAI` section:

| Setting | What it is | Example |
|---|---|---|
| `Endpoint` | Your resource URL | `https://my-resource.services.ai.azure.com/` |
| `Deployment` | The model deployment name you created | `gpt-4.1-mini` |
| `ApiKey` | Your API key | `abc123...` |

Pricing lives in `appsettings.json` under `Pricing` (`PerMillionInputUsd` and
`PerMillionOutputUsd`). Update it to match your model, or experiment 4's dollar
figures will be wrong.

That file is **gitignored**, so your key is never committed. Do not put a key in
`appsettings.json` — that one *is* tracked.

```bash
dotnet run              # run all nine, start to finish
dotnet run -- 5         # run only experiment 5
dotnet run -- 1 3 5     # run a subset
dotnet run -- step      # pause for Enter between each one
dotnet run -- list      # show the menu
```

**Experiments 8 and 9 need no API key at all** — they are pure arithmetic:

```bash
dotnet run -- 8 9
```

A full run costs **well under one cent** (about $0.002).

### If something goes wrong

| Symptom | Cause | Fix |
|---|---|---|
| `DeploymentNotFound` | The `Deployment` name does not exist on your resource | List your real deployments: `GET {endpoint}/openai/deployments?api-version=2023-03-15-preview` with an `api-key` header |
| Config changes seem ignored | `appsettings*.json` is copied to the build output | Run `dotnet build` (not `dotnet run --no-build`) |
| `endpoint not configured` | Still holds the template placeholder | Edit `appsettings.Development.json`, then rebuild |

---

## The nine experiments

| # | Question it answers | Needs API? |
|---|---|---|
| 1 | What actually goes on the wire? | yes |
| 2 | Why does the model forget everything? | yes |
| 3 | Why does a GUID cost more than a sentence? | yes |
| 4 | Where does the money actually go? | yes |
| 5 | **Why is the first token slow — and how much of that is even the model?** | yes |
| 6 | What is streaming really? | yes |
| 7 | **Why can't I write `Assert.Equal` against this?** | yes |
| 8 | **Why is generating text so inefficient?** | no |
| 9 | Why is my request processed alongside strangers' requests? | no |

If you only run one, run **5**. The bolded rows are the ones most likely to
change how you think.

---

## What each experiment found

Below are **real results from real runs**, with the reasoning spelled out. Your
numbers will differ slightly — that variation is itself one of the lessons.

---

### 1. What actually goes on the wire

**Question:** what is an AI model call, mechanically?

**What we sent** — this is 100% of it:

```json
{
  "messages": [
    { "role": "system", "content": "You are terse. One sentence maximum." },
    { "role": "user",   "content": "What is the capital of France?" }
  ],
  "max_tokens": 50
}
```

**What came back:**

```json
{
  "message":       { "role": "assistant", "content": "Paris." },
  "finish_reason": "stop",
  "usage":         { "prompt_tokens": 26, "completion_tokens": 3, "total_tokens": 29 }
}
```

Request size: **156 bytes**. Wall clock: **~800 ms**.

**What this establishes**

There is no session, no connection, no handle, no object living on a server with
your name on it. You send an array of messages; you get one message back. That
is the entire integration.

Two fields deserve permanent attention.

**`finish_reason`** tells you *why* generation stopped:

- `"stop"` — the model finished naturally. Good.
- `"length"` — **you hit your `max_tokens` limit and the answer is cut off.**

We proved the second case by asking for the 20 largest countries with
`max_tokens: 40`. The reply stopped mid-sentence, at country #1:

```
Here is a list of the 20 largest countries by total area...
1. **Russia** – 17,098,242 km²
2.

finish_reason = "length"   <-- LOOK AT THIS
```

That response was **HTTP 200**. No exception. No error field. Nothing in any
monitoring system fires. If you parse it as JSON downstream it breaks; if you
show it to a user they see a sentence that just stops.

This is your first encounter with the failure mode that runs through this whole
project: **the system fails by lying quietly, not by erroring.**

**`usage`** is what you are billed for, and the only honest measure of how
expensive your prompt design really is.

> **A bug we found in our own code here.** This experiment originally printed a
> tidy C# object instead of the raw response. That looked fine — but it silently
> discarded fields the server was sending, including two that later turned out
> to be the most valuable data in the entire project (see experiment 5). Printing
> the *actual* response body is the only reason we found them.

---

### 2. Why the model forgets everything

**Question:** does the model remember previous messages?

Three calls, seconds apart:

| Call | What we did | Reply |
|---|---|---|
| **A** | "Remember the number 8829." | `OK` |
| **B** | Brand new request: "What number did I tell you?" | *"I don't have a number stored from you."* |
| **C** | Same question, but we **resent the history ourselves** | `8829` |

**What this establishes**

Call B failed. Call C worked. Same model, same question, same minute. The only
difference is that in C we put the earlier messages back into the request.

**"Memory" is not a model feature. It is an array on your side that you resend
on every single call.**

Two consequences worth internalising:

1. **You are writing the model's side of the conversation.** In call C we
   supplied the assistant's previous reply ourselves. Nothing verified it.
   Nothing checked the model ever said "OK". You can put words in its mouth —
   and several legitimate prompting techniques do exactly that.

2. **Long conversations get expensive fast.** A 50-turn conversation resends all
   50 turns on turn 51. Cost and latency grow with the length of the
   *conversation*, not the length of your message. Every framework's "memory"
   feature is managing this array for you.

---

### 3. Why a GUID costs more than a sentence

**Question:** you pay per token — so what is a token, really?

Ten samples, measured:

| Sample | Characters | Tokens | Characters per token |
|---|---:|---:|---:|
| plain English | 44 | 17 | 2.59 |
| C# code | 46 | 22 | 2.09 |
| a GUID | 36 | 25 | 1.44 |
| French | 44 | 14 | **3.14** |
| Hindi | 43 | 21 | 2.05 |
| Japanese | 15 | 20 | 0.75 |
| base64 blob | 44 | 28 | 1.57 |
| indented JSON | 30 | 29 | 1.03 |
| minified JSON | 19 | 20 | 0.95 |
| a single `.` | 1 | 8 | **0.12** |

**Spread between best and worst: 25×.** Same API, same price per token, wildly
different cost per character.

**Why this happens**

The tokenizer was built by **BPE (Byte Pair Encoding)**: an offline process that
repeatedly merged the most frequent adjacent character pairs in a huge training
corpus into single tokens. It is **learned compression, not a language rule**.
Text that looked like the training data compresses well. Text that did not,
does not.

**Three findings from the table**

1. **Do not trust the folklore.** The widely repeated claim is "non-English costs
   2–3× more". In our run **French was the cheapest sample of all** — cheaper
   than English. That old claim was true of an older tokenizer (~100k
   vocabulary); current ones (~200k) spent much of that extra vocabulary on
   multilingual merges. Latin-script European languages are now near parity.
   Japanese and Hindi are still worse per character, but far better than they
   were. **Measure it for your model rather than assuming.**

2. **Randomness is incompressible, permanently.** GUIDs and base64 sit near 1
   character per token and always will, because no merge can exist for a
   sequence that never repeats. If you paste hashes, IDs, or base64 images into
   prompts, you pay near-worst-case rates. This is not fixable by a better
   tokenizer.

3. **Formatting whitespace is pure waste.** Identical JSON data cost **29 tokens
   indented vs 20 minified — a 1.4× tax** for zero benefit, since the model does
   not care about indentation. Minifying JSON in prompts is one of the very few
   completely free optimisations available.

**And one surprise:** a single `.` cost **8 tokens**. Every message is wrapped in
invisible role markers before the model sees it:

```
<|im_start|>user\n.<|im_end|>\n<|im_start|>assistant\n
```

You pay that overhead *per message*. Fifty short messages pay it fifty times,
before a single word of your content.

---

### 4. Where the money goes

**Question:** which costs more — reading or writing?

| Case | In | Out | $ in | $ out | $ total |
|---|---:|---:|---:|---:|---:|
| short in, short out | 12 | 2 | 0.000005 | 0.000003 | 0.000008 |
| short in, **long out** | 18 | 326 | 0.000007 | **0.000522** | 0.000529 |
| **long in**, short out | 1822 | 9 | 0.000729 | 0.000014 | 0.000743 |

Total for the experiment: **$0.00128**.

**Output tokens cost 4× more than input tokens**, per token. For `gpt-4.1-mini`
that is $0.40 per million in, $1.60 per million out.

**That ratio is not a pricing decision — it is physics on an invoice:**

- **Input** is processed in **one parallel pass** over the whole prompt
  (prefill). The GPU does large matrix multiplications. Efficient.
- **Output** is generated **one token at a time** (decode). Each token requires
  reading the *entire* model's weights out of GPU memory. Deeply inefficient —
  experiment 8 measures just how inefficient.

**So both levers matter, differently:**

- Reduce input → better retrieval, cache-aware prompt layout, minified JSON
- Reduce output → ask for terse or structured replies, set `max_tokens` honestly

**Now extrapolate to an agent.** A 10-step agent loop does **not** cost 10× a
single call. Each step resends a context that grew by the previous step's
output. Cost grows roughly **quadratically** with step count. This is why agent
bills surprise teams who reasoned linearly.

---

### 5. Why the first token is slow — the most important experiment

**Question:** where does the waiting time actually go?

This one has three findings, and the third is the reason to run it.

#### Attempt 1: measure from the client (and fail honestly)

We sent three prompt variants, five times each, and took medians:

| variant | prompt tokens | median TTFT | spread across 5 runs |
|---|---:|---:|---|
| short | 21 | 1258 ms | 1048–1408 ms |
| long, cacheable | 3522 | 1317 ms | 1125–1440 ms |
| long, random | 3519 | 1305 ms | 842–1580 ms |

A 3,500-token prompt took about the **same** time as a 21-token prompt. The
theory says longer prompts take longer to read. The measurement disagreed.

**The measurement was not wrong — it was not sensitive enough.**

Look at the spread column: the *short* prompt alone varied by **±360 ms** between
runs where nothing changed. That is the **noise floor**. Any effect smaller than
360 ms is invisible here, no matter how real it is.

> **This is the transferable skill.** Know how much your measurement moves when
> nothing changes, *before* you claim an effect. Most published AI latency
> comparisons skip this step, which is why they contradict each other.

#### Attempt 2: read the whole response

The server had been telling us the answer the entire time, in a field called
`usage.latency_checkpoint` — timings measured **inside the service**, with the
network excluded:

```
variant            in tok   cached  engine TTFT   pre-inf   client TTFT
short                  21        0        38 ms    124 ms       1258 ms
long, cacheable      3522     3456        41 ms    123 ms       1317 ms
long, random         3510        0       100 ms    128 ms       1305 ms
```

**Finding A — prefill does scale with prompt length.**

```
  21 tokens ->  38 ms of engine prefill
3510 tokens -> 100 ms of engine prefill   (2.6x)
```

It was never invisible. It was 100 ms hiding under 360 ms of network jitter.

**Finding B — prefix caching, measured exactly.**

Compare rows two and three. Both are ~3,500 tokens, both do the same task. The
only difference is whether the prompt's opening text is **identical each time**
or **different each time**.

```
long, cacheable : 3456 of 3522 prompt tokens served from cache   (98%)
long, random    :    0 of 3510 prompt tokens served from cache   (0%)

long, cacheable :  41 ms of prefill
long, random    : 100 ms of prefill      (2.4x the work)
```

**Prefix caching** means the provider recognises that it has already processed
the beginning of your prompt and reuses that work instead of redoing it. Cached
tokens are also **billed at a quarter of the normal rate** — $0.10 per million
instead of $0.40.

The practical rule follows directly:

> **Put stable content FIRST** (system prompt, policy text, examples).
> **Put volatile content LAST** (user input, timestamps, IDs).

One volatile token near the front invalidates the cache for everything after it.
A timestamp or request ID at the top of a prompt quietly turns a 98% hit rate
into 0%. Nothing errors. Nobody notices until someone reads the bill.

**Finding C — most of your latency is not the model.**

Read the last two columns together:

```
engine prefill : ~40 ms      <- the model actually working
client TTFT    : ~1300 ms    <- what you experience
```

**Over 90% of what you would call "model latency" is routing, queueing, TLS and
network.** If you were asked to make this endpoint feel faster, the model is the
wrong place to look — and that conclusion is invisible from the client and
obvious from one field in the response body.

#### And the timing we got wrong

We also tried to measure **TPOT** (time per output token) by timestamping each
piece of the streamed response. It reported **0.23 ms per token**.

That is impossible. Every token requires a full pass through the model —
milliseconds, not microseconds. What actually happened is that the provider
generated many tokens and sent them in a single network write, so we were timing
our own socket reads, not the model.

The server's own clock gives the real figure:

```
your client measured   0.23 ms per token
the engine reports     6.00 ms per token   <-- the real one
```

**About 26× wrong — in the direction that made things look faster.**

Note that nothing errored. The number was well-formatted, plausible, and
completely meaningless. Measurement bugs are rarely neutral; they tend to favour
whatever you were hoping to see, which is exactly why you should check hardest
when the result is good news.

---

### 6. What streaming actually is

**Question:** when text appears word by word, what is really happening?

The raw chunks, in arrival order:

```
"Hello" | " there" | "," | " my" | " friend" | "."
```

Those ragged pieces are not a network artifact — **those are the tokens**. Note
that `" there"` includes its leading space, and `","` arrives alone. That is what
the tokenizer produced.

Streaming uses **Server-Sent Events (SSE)**: an ordinary HTTP response held open,
emitting `data:` lines until it finally sends `data: [DONE]`.

**But look at the arrival timeline:**

```
    454  (+   454)  ############################ "Hello"
    454  (+     0)   " there"
    454  (+     0)   ","
    455  (+     0)   " my"
    455  (+     0)   " friend"
    455  (+     0)   "."
```

All six arrived in the same millisecond. So we tested a longer generation:

```
chunks              : 239
distinct flushes    : 6        (gaps >= 0.5 ms)
chunks per flush    : 39.8
median non-zero gap : 18.2 ms
```

239 tokens arrived in **6 network writes**, about 40 tokens each. You are
measuring the provider's **flush policy**, not the model's generation speed.

So this experiment shows you the correct **token boundaries** — which is its
point — but not true generation timing. For that, experiment 5 reads the
engine's own clock and experiment 8 derives an independent figure from hardware.

**Two things the API quietly does for you here:**

1. **Detokenization.** Token IDs → bytes → text, buffered until a complete UTF-8
   character exists. That buffering is why chunk boundaries look arbitrary, and
   why an emoji may arrive as one chunk after a pause.
2. **Hiding token IDs entirely.** The model never saw your string — it saw an
   array of integers. The tokenizer runs **server-side**. That is why you send
   text rather than IDs, and why you cannot know your exact token count before
   sending.

**Streaming makes nothing faster.** It changes which number the user perceives —
from total time to time-to-first-token. It is a UX technique, and a good one.

---

### 7. Same input, different output

**Question:** can I test this like normal code?

Five identical requests, twice over.

**`temperature: 1.0`** (the default — sample from the probability distribution):

```
Brew & Bloom  |  Brew Haven  |  Brew & Bloom Café  |  Brew & Bloom Café  |  Brew & Bliss Café
distinct: 4 / 5
```

**`temperature: 0.0`** (greedy — always take the single most likely token):

```
Brew & Bloom Café  |  Brew & Bloom Café  |  Brew & Bloom  |  Brew & Bloom Café  |  Brew & Bloom Café
distinct: 2 / 5
```

**Read that second result again.** Temperature 0 is supposed to be deterministic.
Identical bytes on the wire, greedy decoding, and it *still* disagreed with
itself.

**Why:** your request is processed in a batch alongside other people's requests
(experiment 9 explains why). GPU floating-point addition is not associative —
`(a + b) + c` can differ from `a + (b + c)` in the last decimal place. Different
batch neighbours mean a different summation order, a slightly different number,
and occasionally a different "most likely" token. Once one token differs, the
rest of the sentence can diverge completely.

**You cannot write `Assert.Equal` against this.** Not "should not" — *cannot*.

That single fact is why evaluating AI systems is a **discipline** rather than a
test suite. The right question is never:

> ~~"Is the output correct?"~~

It is:

> **"Over N runs, what fraction were correct — and what do the failures have in
> common?"**

That metric has a name: **`consistency@k`**. Building a harness for it is the
natural next project after this one.

---

### 8. Why generating text is so inefficient (no API key needed)

**Question:** why is decode so much slower than prefill?

This experiment is pure arithmetic. It needs no credentials and no network.

**The key concept: arithmetic intensity (AI)**

```
arithmetic intensity = FLOPs performed / bytes moved from memory
```

It answers: *for every byte I drag out of memory, how much math do I do with it?*
Every GPU has a **ridge point** — the intensity at which it stops starving for
data and starts being limited by math.

| GPU | Memory bandwidth | Peak compute | Ridge point |
|---|---:|---:|---:|
| H100 | 3350 GB/s | 989 TFLOP/s | **295 FLOP/byte** |
| A100 | 2039 GB/s | 312 TFLOP/s | 153 FLOP/byte |

Now the two phases, for a 70-billion-parameter model at 2 bytes per parameter
(**140 GB of weights**):

**Decode — generating ONE token:**
```
bytes moved : 140 GB    (the entire model, for every single token)
FLOPs       : 140 GFLOP
AI          = 1.0 FLOP/byte
```

An H100 needs **295** to be busy. Decode delivers **1.0**.

> **You are using roughly 0.34% of the GPU's compute capability.** It is almost
> entirely idle, waiting on memory.

**Prefill — reading 1000 prompt tokens:**
```
bytes moved : 140 GB    (the same weights, ONCE, for all 1000 tokens)
FLOPs       : 140 TFLOP
AI          = 1000 FLOP/byte
```

Well past the ridge point. **Prefill is compute-bound. Decode is memory-bound.**
Same model, same GPU, same request — opposite bottlenecks, milliseconds apart.

**A prediction from physics alone**

If decode really is bandwidth-bound, token rate should be almost exactly:

```
memory bandwidth / model size = 3350 GB/s / 140 GB = 23.9 tokens/sec
```

Published figures for 70B models on a single H100 land in the 20–30 tok/s range.
That prediction used no benchmark, no profiler, and no knowledge of the
architecture beyond parameter count.

**Now run it backwards**

Experiment 5 recovered a real figure from the server: **6.0 ms per token**. Turn
the equation around:

```
bytes per token = 6.0 ms x 3350 GB/s = 20 GB of weights
  at 2 bytes/parameter -> ~10 billion parameters
  at 1 byte/parameter  -> ~20 billion parameters
```

Treat that as an order of magnitude, not a measurement — it assumes H100-class
hardware, ignores other memory traffic, and your request was batched, which
pushes the estimate upward. But sit with what happened: **from one timing field,
with no architecture details and no insider information, you bounded the size of
a proprietary model to within an order of magnitude.**

That is what it means for a bottleneck to be *real*. When a system is pinned
against physics, the physics tells you about the system.

**Why the 0.3% number explains the industry**

- **Why memory sold out before GPUs did.** If decode is bandwidth-bound, the
  scarce resource is bandwidth, not compute. The H200 is an H100 with more and
  faster memory and *identical* compute. That product exists because of this
  ratio.
- **Why quantisation is so effective.** Halving bytes per parameter nearly halves
  decode latency, because you move half as much memory. It buys speed directly,
  not just space.
- **Why Mixture-of-Experts models exist.** They activate only a fraction of
  parameters per token, so fewer bytes move. A bandwidth optimisation wearing an
  architecture costume.

---

### 9. Why you share a GPU with strangers (no API key needed)

**Question:** if one request wastes 99.7% of a GPU, how is this affordable?

**The key insight: one load of the weights can serve many requests.**

The weights move from memory to the compute units once per step regardless of
how many sequences are in the batch. Bytes stay constant while the math
multiplies. Arithmetic intensity rises linearly with batch size — for free.

| Batch | AI (FLOP/byte) | % of ridge point | tokens/sec total | tokens/sec each |
|---:|---:|---:|---:|---:|
| 1 | 1 | 0.3% | 24 | 23.9 |
| 4 | 4 | 1.4% | 96 | 23.9 |
| 16 | 16 | 5.4% | 383 | 23.9 |
| 64 | 64 | 21.7% | 1531 | 23.9 |
| 128 | 128 | 43.4% | 3063 | 23.9 |
| 256 | 256 | 86.7% | 6126 | 23.9 |

Read the last two columns carefully:

- **tokens/sec total** rises roughly linearly with batch size → *throughput*
- **tokens/sec each** stays flat → *your latency is unchanged*

Batching is nearly **free throughput**, until intensity crosses the ridge point
at 295, after which you are genuinely compute-bound and further batching starts
costing per-request latency.

**What this explains**

- **Why your request is batched with strangers'.** At batch 1 a provider wastes
  99.7% of the GPU. At batch 128 they are near the ridge. Serving you alone would
  cost roughly 100× more. This is also the direct cause of experiment 7 — your
  batch neighbours change the floating-point summation order.
- **Why "continuous batching" was a breakthrough.** Naive batching waits for
  every sequence to finish, so one long generation stalls 127 short ones.
  Continuous batching evicts finished sequences and admits new ones every step,
  keeping the batch full. It is work-stealing for token generation, and it
  roughly 2–4×'d industry throughput.
- **Why KV cache memory is the real limit.** If batching is free throughput, why
  not batch 10,000? Because each sequence needs its own **KV cache** (the stored
  intermediate state for tokens already processed), and that lives in the same
  memory as the weights. Maximum batch size — and therefore a provider's entire
  cost structure — is set by how much KV cache fits.
- **Why PagedAttention mattered.** By removing memory fragmentation it took KV
  cache utilisation from ~20–40% to over 90% → bigger batches → lower cost per
  token. A memory-management technique from 1960s operating systems is
  responsible for a large share of the price drop in AI inference.

---

## Mistakes we made building this, and what they teach

These are worth more than the results, because they are the kind of error that
produces a *confident wrong answer* rather than a crash.

**1. A control group contaminated by the effect it was controlling for.**

Experiment 5 needed an "uncacheable" prompt. It generated random text using
`new Random(12345)` — a **fixed seed**. That produces the *same* "random" text on
every run, so the provider cached it happily and the control reported **98%
cached**. The experiment was measuring the very thing it was supposed to rule
out. Fixed by using `Guid.NewGuid()`, which is unique across runs.

*Lesson: "random" is not the same as "unique". Check your control group produces
the value you expect — here, exactly zero cache hits.*

**2. A helper function that was right for one use and wrong for another.**

A `Median()` helper skipped zero values — correct for latencies, where zero means
"field missing". Then it was reused for **cached token counts**, where zero is
the single most meaningful value there is. Cache misses vanished from the
average, making caching look universal.

*Lesson: when you reuse a helper, re-check its assumptions in the new context.*

**3. Printing a tidy object instead of the raw response.**

Experiment 1 originally serialised a C# record. It looked correct. It silently
dropped `usage.latency_checkpoint` and `prompt_tokens_details.cached_tokens` —
the two fields that made experiment 5's real findings possible.

*Lesson: before building a harness to measure something through a noisy channel,
read the entire raw response. Providers ship far more telemetry than their SDKs
expose, and every library that maps responses onto a neat typed object throws
some of it away.*

---

## Files

| File | What it contains |
|---|---|
| `RawModelClient.cs` | The entire integration — one HTTP POST, plus SSE parsing that timestamps every chunk |
| `Experiments.cs` | Experiments 1–7 (real API calls) |
| `HardwareMath.cs` | Experiments 8–9 (arithmetic only, no network) |
| `Program.cs` | Configuration loading and the experiment runner |
| `Ui.cs` | Console formatting |
| `appsettings.json` | Endpoint, deployment and pricing. **Tracked — no secrets** |
| `appsettings.Development.json` | Your API key. **Gitignored** |

The project deliberately depends on only three configuration packages. **No AI
SDK, no agent framework, no Azure client library** — that is the point.

---

## Checklist: you are done when you can explain, without notes

- [ ] Why an AI call has no session or server-side state
- [ ] Why "memory" is your array, and what a 50-turn conversation really sends
- [ ] Why `finish_reason: "length"` is dangerous despite HTTP 200
- [ ] Why a GUID costs more than a sentence of the same length
- [ ] Why generating 1,000 tokens costs ~4× reading 1,000 tokens
- [ ] The difference between prefill and decode, and which bottleneck each hits
- [ ] What fraction of your endpoint's latency is actually inference
- [ ] Why putting stable content first can cut input cost by 4×
- [ ] Why you must state your noise floor before claiming a latency result
- [ ] Why `temperature: 0` still is not reproducible
- [ ] Why decode uses ~0.3% of a GPU, and why batching is the escape hatch
- [ ] How to estimate a hosted model's size from its per-token latency
- [ ] The one failure mode that no standard monitoring catches

---

## What comes next

Experiment 7 sets up the real problem: identical input, different output. You
cannot write `Assert.Equal` against it, so correctness has to become a **measured
rate** rather than a true/false answer.

The answer is a harness that runs one task N times and reports how often it
quietly gets it wrong — **`consistency@k`**. Everything needed to build it
already exists in this project: the raw client, cost accounting, and the
repeat-and-take-medians plumbing from experiment 5.

It is essentially flaky-test triage and availability math, applied to a component
that fails by producing confident, well-formatted, wrong output with a 200 OK.
