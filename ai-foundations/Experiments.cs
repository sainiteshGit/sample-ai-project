using System.Text.Json;

namespace Lab01;

/// <summary>
/// Seven experiments. Each one isolates a single fact about model calls that
/// you will rely on for the rest of your career. Run them in order.
/// </summary>
internal sealed class Experiments(RawModelClient client, double priceIn, double priceOut)
{
    /// <summary>Recorded by experiment 5 so experiment 8 can compare against physics.</summary>
    public double LastMeasuredTpotMs { get; private set; }
    // ======================================================================
    // 1. What actually goes on the wire
    // ======================================================================
    public async Task TheWireAsync()
    {
        Ui.Header(1, "What actually goes on the wire");

        Msg[] messages =
        [
            Msg.System("You are terse. One sentence maximum."),
            Msg.User("What is the capital of France?"),
        ];

        var body = RawModelClient.BuildBody(messages, maxTokens: 50);

        Console.WriteLine("\n  >>> REQUEST BODY -- this is 100% of what you send:\n");
        Ui.Json(body);

        var (doc, elapsed, bytes) = await client.SendAsync(body);
        var root = doc.RootElement;
        var choice = root.GetProperty("choices")[0];

        Console.WriteLine("\n  >>> RESPONSE BODY -- the parts that matter:\n");
        Ui.Json(new
        {
            message = new
            {
                role = choice.GetProperty("message").GetProperty("role").GetString(),
                content = choice.GetProperty("message").GetProperty("content").GetString(),
            },
            finish_reason = choice.GetProperty("finish_reason").GetString(),
            // Pass the raw JsonElement through, not our C# record -- otherwise
            // PascalCase property names would leak into output that claims to
            // show you the wire. The real field names are snake_case.
            usage = root.GetProperty("usage"),
        });

        Console.WriteLine($"\n  request size: {bytes} bytes    wall clock: {elapsed.TotalMilliseconds:F0} ms");

        // Now deliberately truncate, to show the failure mode.
        var truncated = RawModelClient.BuildBody(
            [Msg.User("List the 20 largest countries by area, with their sizes.")],
            maxTokens: 40);
        var (doc2, _, _) = await client.SendAsync(truncated);
        var c2 = doc2.RootElement.GetProperty("choices")[0];

        Console.WriteLine("\n  >>> Same API, max_tokens=40, a question needing far more:\n");
        Console.WriteLine("  " + c2.GetProperty("message").GetProperty("content").GetString()?.Replace("\n", "\n  "));
        Console.WriteLine($"\n  finish_reason = \"{c2.GetProperty("finish_reason").GetString()}\"   <-- LOOK AT THIS");

        Ui.Note("""
        THE WHOLE INTEGRATION IS A JSON POST.

        No session. No connection. No handle. No object living on a server with
        your name on it. You sent an array of messages; you got an array back.
        HTTP 200 both times.

        Two fields deserve permanent attention:

          finish_reason -- WHY generation stopped.
              "stop"   = the model decided it was done. Good.
              "length" = you hit max_tokens. YOUR OUTPUT IS TRUNCATED.

              That second call returned HTTP 200 with a confident, well-formed,
              INCOMPLETE answer. No exception. No error field. Nothing in your
              monitoring stack fires. If you parse that as JSON downstream, it
              fails; if you show it to a user, they see a sentence that stops.

              This is your first taste of the one genuinely new failure mode:
              the system fails by lying quietly rather than by erroring.

          usage -- what you are billed for, and the only honest measure of how
              expensive your prompt design actually is.
        """);
    }

    // ======================================================================
    // 2. The model has no memory
    // ======================================================================
    public async Task NoMemoryAsync()
    {
        Ui.Header(2, "The model has no memory (proof)");

        Console.WriteLine("\n  Call A -- tell it a number:\n");
        var a = await AskAsync([Msg.User("Remember this number: 8829. Reply with just: OK")], 20);
        Console.WriteLine("    -> " + a);

        Console.WriteLine("\n  Call B -- brand new request, ask for it back:\n");
        var b = await AskAsync([Msg.User("What number did I ask you to remember?")], 60);
        Console.WriteLine("    -> " + b);

        Console.WriteLine("\n  Call C -- same question, but WE resend the history:\n");
        var c = await AskAsync(
        [
            Msg.User("Remember this number: 8829. Reply with just: OK"),
            Msg.Assistant("OK"),
            Msg.User("What number did I ask you to remember?"),
        ], 60);
        Console.WriteLine("    -> " + c);

        Ui.Note("""
        Call B failed. Call C worked. Same model, same question, seconds apart.

        The only difference is that in C we put the history back into the request
        ourselves. "Memory" is not a model feature. It is a client-side data
        structure that YOU resend on every single call.

        Look closely at call C: we WROTE the assistant's previous reply. Nothing
        verified it. Nothing checked the model ever said "OK". You can put words
        in the model's mouth, and several prompting techniques do exactly that.

        What this costs you in production:
          a 50-turn conversation resends all 50 turns on turn 51.
          Cost and latency grow with CONVERSATION length, not message length.
          Every agent framework's "memory" feature is managing this array.
        """);
    }

    // ======================================================================
    // 3. Tokens are not words
    // ======================================================================
    public async Task TokensAsync()
    {
        Ui.Header(3, "Tokens are not words (and you pay per token)");

        (string Label, string Text)[] samples =
        [
            ("plain English",   "The quick brown fox jumps over the lazy dog."),
            ("C# code",         "var x = arr.Where(i => i.Id != null).ToList();"),
            ("a GUID",          "550e8400-e29b-41d4-a716-446655440000"),
            ("French",          "L'accord commercial international est signe."),
            ("Hindi",           "\u0905\u0928\u094D\u0924\u0930\u094D\u0930\u093E\u0937\u094D\u091F\u094D\u0930\u0940\u092F \u0935\u094D\u092F\u093E\u092A\u093E\u0930 \u0938\u092E\u091D\u094C\u0924\u093E \u0939\u0938\u094D\u0924\u093E\u0915\u094D\u0937\u0930\u093F\u0924\u0964"),
            ("Japanese",        "\u56FD\u969B\u8CBF\u6613\u5354\u5B9A\u304C\u7F72\u540D\u3055\u308C\u307E\u3057\u305F\u3002"),
            ("base64 blob",     "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"),
            ("indented JSON",   "{\n  \"a\": 1,\n  \"b\": [2, 3, 4]\n}"),
            ("minified JSON",   "{\"a\":1,\"b\":[2,3,4]}"),
            ("(one character)", "."),
        ];

        Console.WriteLine();
        Console.WriteLine($"  {"sample",-18}{"chars",6}{"tokens",8}{"chars/token",14}");
        Ui.Rule();

        var results = new List<(string Label, int Chars, int Tokens, double Ratio)>();

        foreach (var (label, text) in samples)
        {
            // max_tokens=1 keeps output cost negligible; prompt_tokens is what we want.
            var body = RawModelClient.BuildBody([Msg.User(text)], maxTokens: 1);
            var (doc, _, _) = await client.SendAsync(body);
            var u = Usage.From(doc.RootElement.GetProperty("usage"));
            var ratio = (double)text.Length / u.PromptTokens;
            results.Add((label, text.Length, u.PromptTokens, ratio));
            Console.WriteLine($"  {label,-18}{text.Length,6}{u.PromptTokens,8}{ratio,14:F2}");
        }

        Ui.Rule();

        // Report what YOUR tokenizer actually did, rather than asserting folklore.
        var best = results.MaxBy(r => r.Ratio);
        var worst = results.MinBy(r => r.Ratio);
        var english = results.First(r => r.Label == "plain English");
        var indented = results.First(r => r.Label == "indented JSON");
        var minified = results.First(r => r.Label == "minified JSON");

        Console.WriteLine($"""

              cheapest per character : {best.Label} ({best.Ratio:F2} chars/token)
              most expensive         : {worst.Label} ({worst.Ratio:F2} chars/token)
              spread                 : {best.Ratio / worst.Ratio:F1}x

              JSON indentation tax   : {indented.Tokens} tokens indented vs {minified.Tokens} minified
                                       for the same data ({(double)indented.Tokens / minified.Tokens:F1}x)
            """);

        Ui.Note($"""
        Every row has a different chars-per-token ratio. Same API, same billing
        rate, wildly different cost per character.

        The tokenizer was built by BPE (Byte Pair Encoding): it repeatedly merged
        the most frequent adjacent byte pairs in its training corpus into single
        tokens. It is LEARNED COMPRESSION, not a language rule. So the ratio for
        any given text depends entirely on whether merges for it were learned.

        WHAT THIS MEANS IN PRACTICE, AND WHY YOU SHOULD NOT TRUST FOLKLORE HERE:

        The commonly repeated claim is "non-English costs 2-3x more". That was
        true of older tokenizers (cl100k, ~100k vocab). Modern ones (o200k,
        ~200k vocab) doubled the vocabulary and spent much of it on multilingual
        merges. On your run above, French may well have come out CHEAPER than
        English -- French accent-free prose compresses very well.

        But the advantage is uneven and script-dependent:

          Latin-script European  -> now roughly at parity with English
          Devanagari, CJK, Thai  -> still noticeably worse per character,
                                    though far better than two years ago

        The honest rule is: DO NOT ASSUME. Measure it, for your model, the way
        this experiment just did. Tokenizer behaviour changes with every model
        generation and it changes your bill.

        WHAT HAS NOT CHANGED, AND WON'T:

          * Entropy is incompressible. GUIDs, hashes, and base64 approach
            1 char/token no matter how large the vocabulary gets, because no
            merge can exist for a random sequence. If you paste base64 images or
            hashes into prompts, you pay near-worst-case rates.

          * Structural whitespace is pure waste. Look at the indentation tax
            above -- identical data, and the pretty-printed version costs
            noticeably more. Minifying JSON in prompts is one of the few
            completely free optimisations available to you.

          * Per-message overhead is real. A single "." costs ~8 tokens, because
            the chat template wraps every message in role markers you never see:

                <|im_start|>user\n.<|im_end|>\n<|im_start|>assistant\n

            You pay that per message. A conversation of 50 short messages pays
            it 50 times, before a single word of content.
        """);
    }

    // ======================================================================
    // 4. Where the money goes
    // ======================================================================
    public async Task CostAsync()
    {
        Ui.Header(4, "Where the money goes");

        var policyDoc = "Below is the company travel policy.\n\n" + string.Concat(
            Enumerable.Repeat(
                "Employees must submit receipts within 30 days of travel. Meal caps " +
                "are $75 domestic and $100 international. Hotel caps are $250 and " +
                "$400 per night respectively. Airfare requires prior approval. ", 45));

        (string Label, string Prompt, int MaxTokens)[] cases =
        [
            ("short in, short out", "Reply with exactly: hi", 10),
            ("short in, long out",  "Write a detailed 250-word explanation of CPU caching.", 400),
            ("long in, short out",  policyDoc + "\n\nWhat is the domestic meal cap?", 20),
        ];

        Console.WriteLine();
        Console.WriteLine($"  {"case",-21}{"in",7}{"out",7}{"$ in",12}{"$ out",12}{"$ total",12}");
        Ui.Rule();

        double grand = 0;
        foreach (var (label, prompt, maxT) in cases)
        {
            var body = RawModelClient.BuildBody([Msg.User(prompt)], maxTokens: maxT);
            var (doc, _, _) = await client.SendAsync(body);
            var u = Usage.From(doc.RootElement.GetProperty("usage"));

            var cin = u.PromptTokens / 1_000_000.0 * priceIn;
            var cout = u.CompletionTokens / 1_000_000.0 * priceOut;
            grand += cin + cout;

            Console.WriteLine($"  {label,-21}{u.PromptTokens,7}{u.CompletionTokens,7}" +
                              $"{cin,12:F6}{cout,12:F6}{cin + cout,12:F6}");
        }

        Ui.Rule();
        Console.WriteLine($"  {"total for this experiment",-21}{"",14}{"",24}{grand,12:F6}");

        Ui.Note($"""
        Output tokens cost {priceOut / priceIn:F0}x more than input tokens, per token.

        That ratio is not arbitrary pricing strategy. It is physics showing up on
        an invoice:

          INPUT  is processed in ONE parallel pass over the whole prompt (prefill).
                 The GPU is doing big matrix multiplies. It is COMPUTE-bound and
                 highly efficient.

          OUTPUT is generated ONE TOKEN AT A TIME (decode). Each token requires
                 reading the ENTIRE model's weights out of GPU memory. It is
                 MEMORY-BANDWIDTH-bound and desperately inefficient -- roughly
                 0.3% of the GPU's peak compute is actually used.

        So both levers matter, but differently:

          reduce input  -> better retrieval, cache-aware prompt layout, minify
          reduce output -> ask for terse/structured output, set max_tokens honestly

        Now extrapolate to an agent. A 10-step agent loop does NOT cost 10x a
        single call. Each step resends a context that grew by the previous step's
        output. Cost grows roughly QUADRATICALLY with step count. This is why
        agent bills surprise teams who reasoned linearly.
        """);
    }

    // ======================================================================
    // 5. TTFT vs TPOT
    // ======================================================================
    public async Task LatencyAsync()
    {
        Ui.Header(5, "TTFT vs TPOT -- why the first token is slow");

        const string task = "Count from 1 to 40, comma separated. Numbers only.";

        // Two long prompts, same length, one crucial difference:
        //   cacheable   -- identical prefix every run, so the provider can reuse
        //                  its KV cache and skip most of the prefill.
        //   uncacheable -- random prefix every run, so prefill must actually run.
        // The gap between them IS prefix caching, measured.
        var fixedPrefix = string.Concat(Enumerable.Repeat(
            "Here is background material which you should completely ignore. ", 350));
        // Guid.NewGuid(), not new Random(seed). A seeded RNG produces the SAME
        // "random" prefix on every program run, so the provider's cache -- which
        // lives for minutes -- happily served it and reported 98% cached. The
        // control needs to be unique across runs, not merely across iterations.
        string RandomPrefix() => string.Concat(Enumerable.Range(0, 115).Select(_ =>
            $"Reference note {Guid.NewGuid()} which you should ignore. "));

        // A single sample is worthless here. Server load, routing, and cache
        // hits move TTFT by hundreds of milliseconds run to run -- easily enough
        // to reverse the result and "disprove" something true. We take medians.
        // This is the same instinct you already have about benchmarking.
        const int Repeats = 5;

        Console.WriteLine($"\n  sampling each variant {Repeats}x (medians reported) ...\n");

        var shortRuns = new List<StreamResult>();
        var cachedRuns = new List<StreamResult>();
        var uncachedRuns = new List<StreamResult>();

        for (var i = 0; i < Repeats; i++)
        {
            shortRuns.Add(await client.StreamAsync(
                RawModelClient.BuildBody([Msg.User(task)], maxTokens: 250, stream: true)));

            cachedRuns.Add(await client.StreamAsync(
                RawModelClient.BuildBody([Msg.User(fixedPrefix + "\n\n" + task)],
                    maxTokens: 250, stream: true)));

            uncachedRuns.Add(await client.StreamAsync(
                RawModelClient.BuildBody([Msg.User(RandomPrefix() + "\n\n" + task)],
                    maxTokens: 250, stream: true)));

            Console.WriteLine($"    run {i + 1}/{Repeats}   short {shortRuns[^1].Ttft.TotalMilliseconds,6:F0}" +
                              $"   long-cached {cachedRuns[^1].Ttft.TotalMilliseconds,6:F0}" +
                              $"   long-random {uncachedRuns[^1].Ttft.TotalMilliseconds,6:F0}   ms TTFT");
        }

        var shortTtft = Median(shortRuns.Select(r => r.Ttft.TotalMilliseconds));
        var cachedTtft = Median(cachedRuns.Select(r => r.Ttft.TotalMilliseconds));
        var uncachedTtft = Median(uncachedRuns.Select(r => r.Ttft.TotalMilliseconds));
        var shortTpot = Median(shortRuns.Select(r => r.TpotMs));

        Console.WriteLine();
        Console.WriteLine($"  {"variant",-16}{"in tok",9}{"TTFT ms",11}{"TTFT spread",18}");
        Ui.Rule();
        Line("short", shortRuns, shortTtft);
        Line("long, cacheable", cachedRuns, cachedTtft);
        Line("long, random", uncachedRuns, uncachedTtft);
        Ui.Rule();

        var shortTok = shortRuns[^1].Usage?.PromptTokens ?? 1;
        var cachedTok = cachedRuns[^1].Usage?.PromptTokens ?? 1;
        var uncachedTok = uncachedRuns[^1].Usage?.PromptTokens ?? 1;

        // Azure only attaches usage.latency_checkpoint to NON-streaming
        // responses -- the streaming usage chunk omits it. So repeat each
        // variant without streaming purely to harvest the server's own clock.
        // (A detail you only ever find by reading the raw response, which is
        //  the entire moral of this experiment.)
        // NOTE the Func here rather than a fixed message array. The first version
        // of this code built the random prompt ONCE and sent it three times --
        // so probes 2 and 3 hit the cache created by probe 1, and the
        // "uncacheable" control reported ~98% cached. The experiment was
        // measuring the effect it was supposed to control for. Regenerating the
        // prefix per call is the fix.
        var srvShort = await ProbeAsync(() => [Msg.User(task)]);
        var srvCached = await ProbeAsync(() => [Msg.User(fixedPrefix + "\n\n" + task)]);
        var srvRandom = await ProbeAsync(() => [Msg.User(RandomPrefix() + "\n\n" + task)]);

        async Task<List<Usage>> ProbeAsync(Func<Msg[]> messages)
        {
            var list = new List<Usage>();
            for (var i = 0; i < 3; i++)
            {
                var (doc, _, _) = await client.SendAsync(
                    RawModelClient.BuildBody(messages(), maxTokens: 60));
                if (doc.RootElement.TryGetProperty("usage", out var u))
                    list.Add(Usage.From(u));
            }
            return list;
        }

        var noiseFloor = shortRuns.Select(r => r.Ttft.TotalMilliseconds).Max()
                       - shortRuns.Select(r => r.Ttft.TotalMilliseconds).Min();

        Console.WriteLine($"""

              Measurement noise on the SHORT prompt alone: +/-{noiseFloor:F0} ms.
              That is your floor. Nothing smaller than it is a result -- and
              prefill for a few thousand tokens is far smaller than it.
            """);

        // ------------------------------------------------------------------
        // The client-side numbers above cannot resolve prefill. But the server
        // has been telling us the truth in a field most people never read:
        // usage.latency_checkpoint. Those timings are taken INSIDE the service,
        // so the network is excluded entirely.
        // ------------------------------------------------------------------
        var haveServer = srvShort.Any(u => u.HasServerTiming);

        if (haveServer)
        {
            Console.WriteLine("""

                  ==========================================================================
                  NOW LOOK AT WHAT THE SERVER TOLD US ALL ALONG
                  ==========================================================================

                  The response carries usage.latency_checkpoint -- timings measured inside
                  the service, with your network path excluded. Same requests, honest clock.
                """);

            Console.WriteLine();
            Console.WriteLine($"  {"variant",-16}{"in tok",9}{"cached",9}{"engine TTFT",13}{"pre-inf",10}{"client TTFT",13}");
            Ui.Rule();
            ServerLine("short", srvShort, shortTtft);
            ServerLine("long, cacheable", srvCached, cachedTtft);
            ServerLine("long, random", srvRandom, uncachedTtft);
            Ui.Rule();

            var engShort = Median(srvShort.Select(u => u.EngineTtftMs));
            var engCached = Median(srvCached.Select(u => u.EngineTtftMs));
            var engRandom = Median(srvRandom.Select(u => u.EngineTtftMs));
            var srvShortTok = srvShort[^1].PromptTokens;
            var srvCachedTok = srvCached[^1].PromptTokens;
            var srvRandomTok = srvRandom[^1].PromptTokens;
            var cachedHit = MedianAll(srvCached.Select(u => (double)u.CachedTokens));
            var randomHit = MedianAll(srvRandom.Select(u => (double)u.CachedTokens));
            var engRatio = engShort > 0 ? engRandom / engShort : 0;

            Console.WriteLine($"""

                  PREFILL, MEASURED PROPERLY

                      {srvShortTok,6} tokens ->{engShort,7:F0} ms of engine prefill
                      {srvRandomTok,6} tokens ->{engRandom,7:F0} ms          ({engRatio:F1}x)

                  There it is. {srvRandomTok / Math.Max(srvShortTok, 1)}x the tokens, {engRatio:F1}x the prefill time. Prefill
                  scales with prompt length exactly as the theory says. It was never
                  invisible -- it was just {engRandom:F0} ms hiding under {noiseFloor:F0} ms of network jitter.

                  PREFIX CACHING, MEASURED PROPERLY

                      long, cacheable : {cachedHit:F0} of {srvCachedTok} prompt tokens served from cache
                      long, random    : {randomHit:F0} of {srvRandomTok} prompt tokens served from cache

                  No stopwatch involved. The provider states outright how many tokens it
                  did not have to re-process, and bills those at the cached rate. For
                  gpt-4.1-mini that is $0.10 per 1M instead of $0.40.

                  Two prompts of near-identical length ({srvCachedTok} vs {srvRandomTok} tokens), doing
                  the same task. The only difference is whether the prefix repeats
                  byte-for-byte -- and the engine clock agrees with the token counts:

                      long, cacheable :{engCached,6:F0} ms of prefill
                      long, random    :{engRandom,6:F0} ms of prefill   ({(engCached > 0 ? engRandom / engCached : 0):F1}x)

                  Same length, same task, {(engCached > 0 ? engRandom / engCached : 0):F1}x the prefill work. One volatile
                  token near the front -- a timestamp, a request ID, a session GUID --
                  would collapse that 98% hit rate to zero and move the random row's
                  numbers onto your bill. Nothing would error. Nobody would notice.
                """);

            Console.WriteLine($"""

                  AND NOW THE REAL POINT

                  Compare the columns. Engine prefill is tens of milliseconds. Your
                  client-side TTFT is over a second. Well over 90% of what you call
                  "model latency" is pre-inference routing, queueing, TLS and network.

                  If you were tasked with making this endpoint feel faster, the model is
                  the wrong place to look. That conclusion is invisible from the client
                  and obvious from one field in the response body.

                  THE HABIT WORTH KEEPING: before building a harness to measure something
                  through a noisy channel, read the entire response. Providers ship far
                  more telemetry than their SDKs surface, and every SDK that maps
                  responses onto a tidy typed object throws fields like this away.
                  Ours nearly did too -- experiment 1 was printing a C# record instead of
                  the wire, and this block was simply not visible.
                """);
        }
        else
        {
            Console.WriteLine("""

                  This provider does not return server-side timings, so prefill stays
                  buried under network noise here. Knowing your noise floor BEFORE you
                  claim an effect is the transferable skill; most published LLM latency
                  comparisons skip it, which is why they disagree with each other.
                """);
        }

        // Prefer the server's honest time-between-tokens over our own, which the
        // network may have made meaningless. Experiment 8 consumes this.
        var serverTbt = Median(srvShort.Select(u => u.EngineTbtMs));
        LastMeasuredTpotMs = serverTbt > 0 ? serverTbt
                           : shortRuns[^1].LooksBuffered ? 0
                           : shortTpot;

        var buffered = shortRuns[^1].LooksBuffered;
        if (buffered)
        {
            var clientTpot = Median(shortRuns.Select(r => r.TpotMs));
            var verdict = serverTbt > 0
                ? $"""
                  And here is the correction, from the same server telemetry:

                      your client measured   {clientTpot,6:F2} ms per token
                      the engine reports     {serverTbt,6:F2} ms per token   <-- the real one

                  Roughly {(clientTpot > 0 ? serverTbt / clientTpot : 0):F0}x wrong, in the direction that flatters the system.
                  Note which way the error went: the broken measurement made things
                  look FASTER. Measurement bugs are rarely neutral -- they tend to
                  favour whatever you were hoping to see, which is precisely why you
                  check them hardest when the result is good news.
                """
                : """
                  This provider gives no server-side per-token timing either, so use
                  the bandwidth-derived figure in experiment 8 instead.
                """;

            Console.WriteLine($"""

                  ------------------------------------------------------------------
                  YOUR TPOT MEASUREMENT WAS IMPOSSIBLE. HERE IS THE PROOF.

                  Most inter-chunk gaps came back under 0.5 ms. Real decode needs a
                  full forward pass per token -- milliseconds, not microseconds.
                  Sub-millisecond gaps cannot happen.

                  What did happen: the provider, a proxy, or your TLS stack buffered
                  many tokens and flushed them in one network write. You were timing
                  your own socket reads, not the GPU.

                {verdict}
                  ------------------------------------------------------------------
                """);
        }

        Ui.Note("""
        TTFT and TPOT are tracked separately because they have OPPOSITE
        bottlenecks. This is the most important latency fact in the field, and it
        is why a single "latency" number is always misleading.

          TTFT  = PREFILL.  Entire prompt processed in one parallel pass.
                            COMPUTE-bound. Scales with prompt length.

          TPOT  = DECODE.   One token per forward pass, each requiring a full
                            read of model weights from HBM.
                            MEMORY-BANDWIDTH-bound. Barely cares about prompt
                            length -- only about model size.

          Total latency = TTFT + (TPOT x output tokens)

        THE CACHED-VS-RANDOM ROWS ARE THE PRACTICAL LESSON -- even when, as often
        happens over the public internet, the timing effect is buried in noise.

        Both long prompts do the same task. The only difference is whether the
        prefix repeats. A repeated prefix lets the provider reuse the KV cache it
        already built, and it is BILLED at the cached-input rate: for
        gpt-4.1-mini that is $0.10 per 1M instead of $0.40. Four times cheaper,
        for a change that is purely about ORDERING.

        Billing is the reliable signal here, not your stopwatch. The cost saving
        shows up in the invoice whether or not you can time it from a laptop.

            Put stable content FIRST (system prompt, policy, few-shot examples).
            Put volatile content LAST (user input, timestamps, IDs).

        One volatile token near the front invalidates the cache for everything
        after it. Teams routinely put a timestamp or request ID at the top of a
        prompt and silently lose the entire benefit -- and nothing errors, so
        nobody notices until someone reads the bill.

        Also note the TTFT spread column. Run-to-run variance on a hosted
        endpoint is large -- you share hardware with strangers. Any latency claim
        from a single sample, yours or a vendor's, is noise.

        Other consequences worth internalising:

          * A long prompt hurts perceived responsiveness, not throughput.
          * A bigger model hurts TPOT much more than TTFT.
          * Optimising one can worsen the other -- batching more requests raises
            TTFT while improving throughput. A real trade serving teams make.
          * Streaming makes NOTHING faster. It changes which number the user
            perceives, from total time to TTFT. A UX trick, and a good one.
        """);

        static void Line(string label, List<StreamResult> runs, double median)
        {
            var ms = runs.Select(r => r.Ttft.TotalMilliseconds).ToArray();
            var tok = runs[^1].Usage?.PromptTokens ?? 0;
            var spread = $"{ms.Min():F0}-{ms.Max():F0} ms";
            Console.WriteLine($"  {label,-16}{tok,9}{median,11:F0}{spread,18}");
        }

        static void ServerLine(string label, List<Usage> us, double clientTtft)
        {
            if (us.Count == 0) return;
            Console.WriteLine($"  {label,-16}{us[^1].PromptTokens,9}" +
                              $"{MedianAll(us.Select(u => (double)u.CachedTokens)),9:F0}" +
                              $"{Median(us.Select(u => u.EngineTtftMs)),13:F0}" +
                              $"{Median(us.Select(u => u.PreInferenceMs)),10:F0}" +
                              $"{clientTtft,13:F0}");
        }

        // Median() drops zeros, which is right for latencies (a zero means the
        // field was absent) and WRONG for token counts, where zero is the most
        // meaningful value there is -- it means nothing was cached.
        static double MedianAll(IEnumerable<double> xs)
        {
            var a = xs.OrderBy(x => x).ToArray();
            return a.Length == 0 ? 0
                 : a.Length % 2 == 1 ? a[a.Length / 2]
                 : (a[a.Length / 2 - 1] + a[a.Length / 2]) / 2;
        }

        static double Median(IEnumerable<double> xs)
        {
            var a = xs.Where(x => x > 0).OrderBy(x => x).ToArray();
            return a.Length == 0 ? 0
                 : a.Length % 2 == 1 ? a[a.Length / 2]
                 : (a[a.Length / 2 - 1] + a[a.Length / 2]) / 2;
        }
    }

    // ======================================================================
    // 6. What streaming actually is
    // ======================================================================
    public async Task StreamingShapeAsync()
    {
        Ui.Header(6, "What streaming actually looks like");

        var r = await client.StreamAsync(RawModelClient.BuildBody(
            [Msg.User("Reply with exactly this and nothing else: Hello there, my friend.")],
            maxTokens: 40, stream: true));

        Console.WriteLine("\n  Raw chunks in arrival order:\n");
        Console.WriteLine("    " + string.Join(" | ",
            r.Chunks.Select(c => "\"" + c.Replace("\n", "\\n") + "\"")));

        Console.WriteLine($"\n  {r.Chunks.Count} chunks  ->  \"{r.Text}\"");
        Console.WriteLine($"  finish_reason = {r.FinishReason}");

        Console.WriteLine("\n  Arrival timeline (ms since request sent):\n");
        for (var i = 0; i < Math.Min(r.ArrivalsMs.Count, 12); i++)
        {
            var gap = i == 0 ? r.ArrivalsMs[0] : r.ArrivalsMs[i] - r.ArrivalsMs[i - 1];
            var bar = new string('#', Math.Min((int)(gap / 2), 50));
            Console.WriteLine($"    {r.ArrivalsMs[i],7:F0}  (+{gap,6:F0})  {bar} {Escape(r.Chunks[i])}");
        }

        // The short reply above is very likely to arrive in one buffered flush.
        // Rather than assert that "longer generations often reveal the real
        // gaps", test it: ask for a long generation and look again.
        var longR = await client.StreamAsync(RawModelClient.BuildBody(
            [Msg.User("Count slowly from 1 to 120, one number per line, numbers only.")],
            maxTokens: 400, stream: true));

        var gaps = Enumerable.Range(1, Math.Max(0, longR.ArrivalsMs.Count - 1))
                             .Select(i => longR.ArrivalsMs[i] - longR.ArrivalsMs[i - 1])
                             .ToArray();
        var flushes = gaps.Count(g => g >= 0.5);

        Console.WriteLine($"""

              Now the same thing with a LONG generation ({longR.Chunks.Count} chunks):

                chunks              : {longR.Chunks.Count}
                distinct flushes    : {flushes}   (gaps >= 0.5 ms)
                chunks per flush    : {(flushes > 0 ? (double)longR.Chunks.Count / flushes : longR.Chunks.Count),0:F1}
                median non-zero gap : {(gaps.Where(g => g >= 0.5).OrderBy(g => g).ToArray() is { Length: > 0 } nz ? nz[nz.Length / 2] : 0),0:F1} ms
            """);

        var longBuffered = longR.LooksBuffered;
        var firstChunks = string.Join(", ",
            r.Chunks.Take(6).Select(c => "\"" + c.Replace("\n", "\\n") + "\""));

        var timingComment = r.LooksBuffered
            ? $"""
        BUT LOOK AT YOUR TIMELINE: the gaps are almost all +0 ms.

        Those tokens arrived in the same millisecond. That cannot be decode --
        each token needs its own forward pass, which takes milliseconds. The
        provider generated a run of tokens, then flushed them in ONE network
        write.

        So you are seeing the correct TOKEN BOUNDARIES (which is the point of
        this experiment) but NOT the true generation timing.

        {(longBuffered
            ? "The long generation was buffered too -- look at 'chunks per flush'\nabove. The response came back in a handful of network writes, each\ncarrying dozens of tokens. You are measuring the provider's flush\npolicy, not the GPU."
            : "The long generation, however, was NOT buffered -- look at its median\nnon-zero gap above. That is much closer to genuine per-token decode\ntime. Buffering depends on response length and provider policy, which\nis exactly why one measurement is never enough.")}

        You cannot fix this from the client. But you do not have to: experiment 5
        pulls the engine's own per-token timing out of usage.latency_checkpoint,
        and experiment 8 derives an independent figure from memory bandwidth.
        Two honest sources beat one convenient stopwatch.
        """
            : """
        Look at the timeline. The first gap is large -- that is prefill, the whole
        prompt processed in one pass. Every gap after it is small and remarkably
        uniform -- that is decode, doing the same fixed amount of work per token,
        over and over. You are watching the two phases separate on screen.
        """;

        Ui.Note($"""
        The chunks are ragged: {firstChunks} ...

        That is not a network artifact. THOSE ARE THE TOKENS. Streaming delivers
        them over Server-Sent Events -- an ordinary HTTP response held open,
        emitting "data:" lines until it sends "data: [DONE]".

        {timingComment}

        Two things the API is quietly doing for you here:

          1. DETOKENIZATION. Token IDs -> bytes -> text, buffered until a complete
             UTF-8 character exists. That buffering is why chunk boundaries look
             arbitrary and why an emoji may arrive as one chunk after a pause.

          2. HIDING TOKEN IDS ENTIRELY. The model never saw your string; it saw
             an array of integers. The tokenizer runs SERVER-SIDE. That is the
             whole reason you send text and not IDs -- and the reason you cannot
             know your exact token count before sending.
        """);

        static string Escape(string s) => "\"" + s.Replace("\n", "\\n") + "\"";
    }

    // ======================================================================
    // 7. Non-determinism
    // ======================================================================
    public async Task NonDeterminismAsync()
    {
        Ui.Header(7, "Same input, different output");

        Msg[] prompt = [Msg.User("Invent a name for a coffee shop. Reply with the name only.")];

        var hot = await SampleAsync(prompt, temperature: 1.0, n: 5);
        Console.WriteLine("\n  temperature = 1.0, five identical requests:\n");
        foreach (var s in hot) Console.WriteLine("    -> " + s);
        Console.WriteLine($"\n    distinct: {hot.Distinct().Count()} / {hot.Count}");

        var cold = await SampleAsync(prompt, temperature: 0.0, n: 5);
        Console.WriteLine("\n  temperature = 0.0 (greedy), five identical requests:\n");
        foreach (var s in cold) Console.WriteLine("    -> " + s);
        Console.WriteLine($"\n    distinct: {cold.Distinct().Count()} / {cold.Count}");

        Ui.Note("""
        This is the property that invalidates every testing instinct you have.

        temperature scales the logits before sampling. At 1.0 you sample from the
        distribution; at 0 you take the argmax every step. So temperature=0 is
        MUCH more repeatable -- but it is still not a guarantee, because
        floating-point reduction order on a GPU depends on batch composition, and
        your request is batched with strangers' requests. Different neighbours,
        different summation order, different last decimal place, occasionally a
        different argmax. Once one token differs, the rest of the sequence can
        diverge completely.

        You cannot write Assert.Equal against this. Not "should not", CANNOT.

        That single fact is why evaluation is a DISCIPLINE rather than a test
        suite, and it is the doorway to the most valuable skill in this repo.

        The right question is never "is the output correct?"
        It is: "over N runs, what fraction were correct, and what do the
                failures have in common?"

        That metric has a name -- consistency@k -- and building a harness for it
        is the natural next project after this one. Your distributed-systems
        instincts transfer directly: this is flaky-test triage and availability
        math, not machine learning.

        Note also what experiment 5 showed you about measurement. Before you can
        say "this prompt is more reliable than that one", you need to know your
        noise floor -- how much the answer moves when NOTHING changes. Same
        discipline, applied to correctness instead of latency.
        """);
    }

    // ------------------------------------------------------------------
    private async Task<string> AskAsync(Msg[] messages, int maxTokens)
    {
        var (doc, _, _) = await client.SendAsync(RawModelClient.BuildBody(messages, maxTokens));
        return doc.RootElement.GetProperty("choices")[0]
            .GetProperty("message").GetProperty("content").GetString()?.Trim() ?? "";
    }

    private async Task<List<string>> SampleAsync(Msg[] prompt, double temperature, int n)
    {
        var results = new List<string>();
        for (var i = 0; i < n; i++)
        {
            var body = RawModelClient.BuildBody(prompt, maxTokens: 20, temperature: temperature);
            var (doc, _, _) = await client.SendAsync(body);
            results.Add(doc.RootElement.GetProperty("choices")[0]
                .GetProperty("message").GetProperty("content").GetString()?.Trim() ?? "");
        }
        return results;
    }
}
