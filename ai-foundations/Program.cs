using Microsoft.Extensions.Configuration;

namespace Lab01;

/// <summary>
/// AI FOUNDATIONS -- everything about a model call, in one project, stepped
/// through one experiment at a time.
///
/// No SDK. No agent framework. Raw HTTP, so nothing is hidden from you.
///
/// The goal is not to build something. The goal is that afterwards you can
/// answer all of these from memory:
///
///   1. What exactly goes on the wire when I "chat" with a model?
///   2. Why does the model have no memory?
///   3. Why do code and GUIDs cost so much more than English?
///   4. Where does my money actually go?
///   5. Why is the first token so much slower than the rest?
///   6. What is streaming really?
///   7. Why can't I write Assert.Equal against this?
///   8. Why is decode memory-bound, and why does that explain the whole industry?
///   9. Why is my request batched with strangers', and why does that cap cost?
///
/// Experiments 1-7 make real API calls. 8-9 are pure arithmetic, no calls.
///
/// Usage:
///   dotnet run              run all nine, straight through
///   dotnet run -- 5         run only experiment 5
///   dotnet run -- 1 3 5     run a subset
///   dotnet run -- step      pause between each one
///   dotnet run -- list      show the menu and exit
/// </summary>
internal static class Program
{
    private sealed record Step(int N, string Name, string Blurb, Func<Task> Run, bool NeedsApi = true);

    private static async Task<int> Main(string[] args)
    {
        var config = new ConfigurationBuilder()
            .SetBasePath(AppContext.BaseDirectory)
            .AddJsonFile("appsettings.json", optional: true)
            .AddJsonFile("appsettings.Development.json", optional: true)
            .AddEnvironmentVariables()
            .Build();

        var endpoint = config["AzureOpenAI:Endpoint"];
        var deployment = config["AzureOpenAI:Deployment"];
        var apiVersion = config["AzureOpenAI:ApiVersion"] ?? "2024-10-21";
        var apiKey = config["AzureOpenAI:ApiKey"];
        var priceIn = double.TryParse(config["Pricing:PerMillionInputUsd"], out var pi) ? pi : 0.40;
        var priceOut = double.TryParse(config["Pricing:PerMillionOutputUsd"], out var po) ? po : 1.60;

        var configured = !string.IsNullOrWhiteSpace(endpoint)
                         && !string.IsNullOrWhiteSpace(deployment)
                         && !string.IsNullOrWhiteSpace(apiKey)
                         && !endpoint!.Contains("your-resource");

        var lab = configured
            ? new Experiments(new RawModelClient(endpoint!, deployment!, apiVersion, apiKey!), priceIn, priceOut)
            : null;

        Step[] steps =
        [
            new(1, "the wire",        "the full JSON request and response, plus silent truncation",
                () => lab!.TheWireAsync()),
            new(2, "no memory",       "three calls proving the model forgets everything",
                () => lab!.NoMemoryAsync()),
            new(3, "tokens",          "why a GUID costs 4x what English costs",
                () => lab!.TokensAsync()),
            new(4, "cost",            "real dollars, and why output costs more than input",
                () => lab!.CostAsync()),
            new(5, "latency",         "TTFT vs TPOT -- the most important latency fact there is",
                () => lab!.LatencyAsync()),
            new(6, "streaming",       "raw SSE chunks and an arrival timeline",
                () => lab!.StreamingShapeAsync()),
            new(7, "non-determinism", "same prompt, different answers -- why tests break",
                () => lab!.NonDeterminismAsync()),
            new(8, "roofline",        "why decode is memory-bound   [no API needed]",
                () => { new HardwareMath(lab?.LastMeasuredTpotMs ?? 0).Roofline(); return Task.CompletedTask; },
                NeedsApi: false),
            new(9, "batching",        "why you are batched with strangers   [no API needed]",
                () => { new HardwareMath(lab?.LastMeasuredTpotMs ?? 0).Batching(); return Task.CompletedTask; },
                NeedsApi: false),
        ];

        if (args.Contains("list"))
        {
            PrintMenu(steps);
            return 0;
        }

        var numeric = args.Where(a => int.TryParse(a, out _)).Select(int.Parse).ToHashSet();
        var selected = numeric.Count > 0 ? steps.Where(s => numeric.Contains(s.N)).ToArray() : steps;

        if (selected.Length == 0)
        {
            Console.WriteLine("\n  No experiment matched. Valid numbers: 1-9.");
            PrintMenu(steps);
            return 1;
        }

        if (!configured)
        {
            var offline = selected.Where(s => !s.NeedsApi).ToArray();
            if (offline.Length == 0)
            {
                PrintMissingConfig();
                return 1;
            }

            Console.WriteLine("""

                  No API credentials configured, so skipping experiments 1-7.
                  Running the arithmetic-only experiments instead.
                  See appsettings.Development.json.template to enable the rest.
                """);
            selected = offline;
        }

        Ui.Banner(
            "AI FOUNDATIONS -- ONE MODEL CALL, COMPLETELY UNDERSTOOD",
            "",
            $"deployment : {(configured ? deployment : "(not configured)")}",
            $"pricing    : ${priceIn}/M in, ${priceOut}/M out   (edit appsettings.json)",
            "",
            $"running    : {string.Join(", ", selected.Select(s => s.N))}");

        // Runs straight through by default. Pass "step" to pause between each.
        var stepwise = args.Contains("step") && selected.Length > 1 && !Console.IsInputRedirected;

        foreach (var s in selected)
        {
            if (stepwise)
            {
                Console.WriteLine();
                Ui.Rule('.');
                Console.WriteLine($"  NEXT  [{s.N} of 9]  {s.Name}");
                Console.WriteLine($"                     {s.Blurb}");
                Console.Write("  Enter = run,  s = skip,  q = quit  > ");
                var key = Console.ReadLine()?.Trim().ToLowerInvariant();
                if (key == "q") break;
                if (key == "s") continue;
            }

            try
            {
                await s.Run();
            }
            catch (Exception ex)
            {
                Console.WriteLine($"\n  !! experiment {s.N} ({s.Name}) failed:\n     {ex.Message}\n");
            }
        }

        PrintSummary();
        return 0;
    }

    private static void PrintMenu(Step[] steps)
    {
        Console.WriteLine("\n  AI FOUNDATIONS -- experiments\n");
        foreach (var s in steps)
            Console.WriteLine($"    {s.N}  {s.Name,-18}{s.Blurb}");
        Console.WriteLine("""

              dotnet run            run all nine, straight through
              dotnet run -- 5       run one
              dotnet run -- step    pause between each one
            """);
    }

    private static void PrintMissingConfig() => Console.WriteLine("""

          Missing configuration.

          Copy appsettings.Development.json.template to
          appsettings.Development.json and fill in your values:

            {
              "AzureOpenAI": {
                "Endpoint":   "https://your-resource.services.ai.azure.com",
                "Deployment": "gpt-4.1-mini",
                "ApiKey":     "your-key-here"
              }
            }

          That file is gitignored, so the key will not be committed.

          Tip: experiments 8 and 9 need no credentials at all:
            dotnet run -- 8 9
        """);

    private static void PrintSummary()
    {
        Ui.Banner("WHAT YOU SHOULD BE ABLE TO SAY NOW");
        Console.WriteLine("""

              THE API SURFACE
               1. An LLM call is a JSON POST. There is no session, no state.
               2. Memory is a client-side array that YOU resend on every call.
               3. finish_reason = "length" is SILENT TRUNCATION with an HTTP 200.
               4. Tokens are BPE merges, not words. Code and GUIDs cost far more.

              THE PHYSICS UNDERNEATH
               5. Prefill is parallel and COMPUTE-bound      -> sets TTFT.
                  Decode is serial and MEMORY-BANDWIDTH-bound -> sets TPOT.
                  Total latency = TTFT + TPOT x output tokens.
               6. That is also why output tokens are priced ~4x input tokens.
               7. At batch 1, decode uses ~0.3% of an H100. Batching is the
                  escape hatch, and KV cache capacity is what caps the batch.
               8. Streaming makes nothing faster. It is a UX trick, a good one.

              MEASUREMENT
               9. On a hosted endpoint, >90% of "model latency" is routing,
                  queueing and network. Engine prefill was ~30 ms under
                  ~1300 ms of client-side TTFT. Optimise the right layer.
              10. Read the WHOLE response. usage.latency_checkpoint and
                  prompt_tokens_details.cached_tokens answered questions that
                  were unanswerable with a stopwatch -- and every SDK that maps
                  responses onto a tidy typed object discards them.
              11. Know your noise floor before you claim an effect, and be
                  most suspicious of measurements that flatter you.

              THE ONE GENUINELY NEW THING
              12. Identical input does not guarantee identical output. Ever.
                  These systems fail by producing confident, well-formatted,
                  WRONG output with a 200 OK. Every monitoring instinct you
                  have assumes failures announce themselves. Here they do not.

              WHERE THIS GOES NEXT
                  Build a harness that runs one task N times and measures how
                  often it silently lies. That metric is consistency@k. It is a
                  distributed-systems problem -- flaky-test triage and
                  availability math -- handed to ML people, which is exactly
                  why it is the most valuable gap you can fill.

            """);
    }
}
