using System.Diagnostics;
using Azure.AI.OpenAI;
using Microsoft.Agents.AI;
using Microsoft.Agents.AI.Workflows;
using Microsoft.Extensions.AI;
using Microsoft.Extensions.Configuration;

namespace WorkflowsBenchmark;

/// <summary>
/// Three-way benchmark comparing how the SAME travel-approval task is handled by:
///
///   A) MonolithicAgent — one agent, one prompt, three jobs (parse + policy + email).
///                        Cheapest call count, but every responsibility competes for
///                        attention in a single context.
///
///   B) SequentialWorkflow — three single-purpose agents wired with
///                           AgentWorkflowBuilder.BuildSequential. Output of agent N
///                           is the input to agent N+1. Each agent stays in its lane.
///
///   C) ConcurrentWorkflow — parser runs first (we need its output), then policy
///                           and email agents fan out in parallel from the parsed
///                           summary. Aggregated into one final response.
///
/// We measure three things per pattern:
///   COST         — total input + output tokens summed across every model call
///   LATENCY      — wall-clock ms for the whole task
///   CORRECTNESS  — substring-match against POLICY-SPECIFIC keywords
///                  (the right verdict word + the right cap dollar amount)
/// </summary>
internal class Program
{
    private record TurnResult(
        string Pattern,
        string PromptLabel,
        long InputTokens,
        long OutputTokens,
        long ElapsedMs,
        int ModelTurns,
        int KeywordHits,
        int KeywordTotal,
        string FinalText);

    static async Task Main()
    {
        IConfiguration config = new ConfigurationBuilder()
            .SetBasePath(Directory.GetCurrentDirectory())
            .AddJsonFile("appsettings.json", optional: true)
            .AddJsonFile("appsettings.Development.json", optional: true)
            .Build();

        string? endpoint   = config["AzureOpenAI:Endpoint"];
        string? apiKey     = config["AzureOpenAI:ApiKey"];
        string  deployment = config["AzureOpenAI:DeploymentName"] ?? "gpt-4.1-mini";

        if (string.IsNullOrWhiteSpace(endpoint))
        {
            Console.Error.WriteLine(
                "Set AzureOpenAI:Endpoint in appsettings.Development.json " +
                "(copy appsettings.Development.json.template).");
            return;
        }

        AzureOpenAIClient openAI = Agents.CreateClient(endpoint, apiKey);

        Console.WriteLine("============================================================");
        Console.WriteLine("  Workflows: Monolithic vs Sequential vs Concurrent");
        Console.WriteLine("============================================================");
        Console.WriteLine($"Model      : {deployment}");
        Console.WriteLine($"Test cases : {Prompts.All.Length}");
        Console.WriteLine();

        var results = new List<TurnResult>();

        foreach (var p in Prompts.All)
        {
            Console.WriteLine($"── Prompt: {p.Label} ──");
            Console.WriteLine($"   {Truncate(p.Text, 110)}");
            Console.WriteLine($"   expected: [{string.Join(", ", p.ExpectedKeywords)}]");

            // A) Monolithic — one agent, one call, three jobs in one prompt.
            var monolithic = Agents.CreateMonolithic(openAI, deployment);
            var monoResult = await RunMonolithicAsync(monolithic, p);
            results.Add(monoResult);
            ReportRow(monoResult);

            // B) Sequential — parser → policy → drafter, output flows downstream.
            var seqAgents = new[]
            {
                Agents.CreateParser(openAI, deployment),
                Agents.CreatePolicyChecker(openAI, deployment),
                Agents.CreateEmailDrafter(openAI, deployment),
            };
            var seqWorkflow = AgentWorkflowBuilder.BuildSequential("travel-seq", seqAgents);
            var seqResult = await RunWorkflowAsync("Sequential", seqWorkflow, p);
            results.Add(seqResult);
            ReportRow(seqResult);

            // C) Concurrent — parser first (sequential), then policy+drafter fan out.
            // We model this as: parser → concurrent(policy, drafter), aggregating
            // both branches into one final message.
            var parser = Agents.CreateParser(openAI, deployment);
            var concurrentInner = AgentWorkflowBuilder.BuildConcurrent(
                "policy-and-draft",
                new[]
                {
                    Agents.CreatePolicyChecker(openAI, deployment),
                    Agents.CreateEmailDrafter(openAI, deployment),
                },
                aggregator: AggregateBranches);
            // Wrap parser+concurrent into a sequential pipeline. We host the
            // inner concurrent workflow as an AIAgent so it can sit on the same
            // sequential conveyor belt as the parser.
            var concurrentWorkflow = AgentWorkflowBuilder.BuildSequential(
                "travel-concurrent",
                new AIAgent[]
                {
                    parser,
                    concurrentInner.AsAgent(
                        id: "policy-and-draft",
                        name: "PolicyAndDraftFanout"),
                });
            var conResult = await RunWorkflowAsync("Concurrent", concurrentWorkflow, p);
            results.Add(conResult);
            ReportRow(conResult);

            // Side-by-side outputs so quality isn't only judged by keyword matches.
            Console.WriteLine();
            foreach (var r in results.Where(x => x.PromptLabel == p.Label))
            {
                Console.WriteLine($"   --- {r.Pattern} final ---");
                foreach (string line in r.FinalText.Split('\n'))
                {
                    Console.WriteLine($"   | {line}");
                }
            }
            Console.WriteLine();
        }

        PrintCorrectnessSummary(results);
        PrintCostSummary(results);
        PrintLatencySummary(results);
    }

    /// <summary>
    /// Aggregator for BuildConcurrent: each inner agent produces a list of messages.
    /// We concatenate them with a header so the caller can see both outputs.
    /// </summary>
    private static List<ChatMessage> AggregateBranches(
        IList<List<ChatMessage>> branches)
    {
        var combined = new List<ChatMessage>();
        for (int i = 0; i < branches.Count; i++)
        {
            string header = i == 0 ? "[POLICY OUTPUT]" : "[EMAIL OUTPUT]";
            string body = string.Join(
                "\n",
                branches[i].Select(m => m.Text ?? string.Empty));
            combined.Add(new ChatMessage(ChatRole.Assistant, $"{header}\n{body}"));
        }
        return combined;
    }

    private static async Task<TurnResult> RunMonolithicAsync(AIAgent agent, Prompts.TestCase p)
    {
        Console.WriteLine($"   [{Timestamp()}] -> Monolithic calling model...");
        var sw = Stopwatch.StartNew();
        AgentResponse response;
        try
        {
            response = await agent.RunAsync(p.Text);
        }
        catch (Exception ex)
        {
            sw.Stop();
            return new TurnResult("Monolithic", p.Label, 0, 0, sw.ElapsedMilliseconds,
                0, 0, p.ExpectedKeywords.Length, $"<error: {ex.Message}>");
        }
        sw.Stop();

        var (inTok, outTok, turns) = SumUsage(response);
        string text = response.Text ?? string.Empty;
        var (hits, total) = Prompts.Score(p, text);

        Console.WriteLine($"   [{Timestamp()}] <- Monolithic done in {sw.ElapsedMilliseconds}ms ({turns} turn{(turns == 1 ? "" : "s")})");
        return new TurnResult("Monolithic", p.Label, inTok, outTok,
            sw.ElapsedMilliseconds, turns, hits, total, text);
    }

    private static async Task<TurnResult> RunWorkflowAsync(
        string patternName, Workflow workflow, Prompts.TestCase p)
    {
        Console.WriteLine($"   [{Timestamp()}] -> {patternName} starting workflow...");
        var sw = Stopwatch.StartNew();
        long inTok = 0, outTok = 0;
        int turns = 0;
        string finalText = string.Empty;
        var seenExecutors = new HashSet<string>();

        try
        {
            // Agent workflows expect a list of ChatMessage as input, not a raw
            // string. Wrap the prompt as a single user message.
            var input = new List<ChatMessage> { new(ChatRole.User, p.Text) };
            await using var run = await InProcessExecution.StreamAsync(
                workflow, input);

            await run.TrySendMessageAsync(new TurnToken(emitEvents: true));

            await foreach (var evt in run.WatchStreamAsync())
            {
                switch (evt)
                {
                    case AgentResponseEvent agentEvt:
                        var (i, o, t) = SumUsageFromResponse(agentEvt.Response);
                        inTok += i;
                        outTok += o;
                        turns += t;
                        break;

                    // Streaming runs may only emit update chunks. Usage is
                    // typically reported as a UsageContent in the final chunk
                    // of each agent's turn — we look for it per executor and
                    // count one turn per distinct executor we see.
                    case AgentResponseUpdateEvent updateEvt:
                        if (seenExecutors.Add(updateEvt.ExecutorId))
                        {
                            turns++;
                        }
                        foreach (var content in updateEvt.Update.Contents)
                        {
                            if (content is UsageContent usage)
                            {
                                inTok  += usage.Details.InputTokenCount  ?? 0;
                                outTok += usage.Details.OutputTokenCount ?? 0;
                            }
                        }
                        break;

                    case WorkflowOutputEvent outEvt:
                        finalText = ExtractText(outEvt);
                        break;
                }
            }
        }
        catch (Exception ex)
        {
            sw.Stop();
            Console.Error.WriteLine($"   [{Timestamp()}] !! {patternName} failed after {sw.ElapsedMilliseconds}ms: {ex.Message}");
            return new TurnResult(patternName, p.Label, inTok, outTok,
                sw.ElapsedMilliseconds, turns, 0, p.ExpectedKeywords.Length,
                $"<error: {ex.Message}>");
        }
        sw.Stop();

        var (hits, total) = Prompts.Score(p, finalText);
        Console.WriteLine($"   [{Timestamp()}] <- {patternName} done in {sw.ElapsedMilliseconds}ms ({turns} model turn{(turns == 1 ? "" : "s")})");
        return new TurnResult(patternName, p.Label, inTok, outTok,
            sw.ElapsedMilliseconds, turns, hits, total, finalText);
    }

    private static (long inTok, long outTok, int turns) SumUsage(AgentResponse response)
    {
        long inTok = 0, outTok = 0;
        int turns = 0;
        foreach (object? raw in EnumerateRawResponses(response))
        {
            if (raw is ChatResponse cr)
            {
                turns++;
                if (cr.Usage is { } u)
                {
                    inTok  += u.InputTokenCount  ?? 0;
                    outTok += u.OutputTokenCount ?? 0;
                }
            }
        }
        return (inTok, outTok, turns);
    }

    private static (long inTok, long outTok, int turns) SumUsageFromResponse(AgentResponse response) =>
        SumUsage(response);

    private static IEnumerable<object?> EnumerateRawResponses(AgentResponse response)
    {
        object? raw = response.RawRepresentation;
        if (raw is null) yield break;
        if (raw is System.Collections.IEnumerable enumerable && raw is not string)
        {
            foreach (object? item in enumerable) yield return item;
        }
        else
        {
            yield return raw;
        }
    }

    private static string ExtractText(WorkflowOutputEvent evt)
    {
        // WorkflowOutputEvent doesn't expose Data directly; use the typed
        // accessors. For agent workflows the payload is typically a list of
        // ChatMessage produced by the last agent (or our aggregator).
        if (evt.Is<List<ChatMessage>>(out var list) && list is not null)
        {
            return string.Join("\n", list.Select(m => m.Text ?? string.Empty));
        }
        if (evt.Is<ChatMessage>(out var single) && single is not null)
        {
            return single.Text ?? string.Empty;
        }
        if (evt.Is<AgentResponse>(out var ar) && ar is not null)
        {
            return ar.Text ?? string.Empty;
        }
        if (evt.Is<string>(out var s) && s is not null)
        {
            return s;
        }
        return evt.ToString() ?? string.Empty;
    }

    // ──────────────────────────── reporting ────────────────────────────

    private static void ReportRow(TurnResult r)
    {
        string score = r.KeywordTotal == 0 ? "n/a" : $"{r.KeywordHits}/{r.KeywordTotal}";
        Console.WriteLine($"   {r.Pattern,-10}: in={r.InputTokens,6}  out={r.OutputTokens,5}  " +
                          $"turns={r.ModelTurns,1}  {r.ElapsedMs,5}ms  correct={score}");
    }

    private static void PrintCorrectnessSummary(IEnumerable<TurnResult> results)
    {
        Console.WriteLine("============================================================");
        Console.WriteLine("  CORRECTNESS — keyword grounding (verdict + policy fact)");
        Console.WriteLine("============================================================");
        var byPattern = results
            .Where(r => r.KeywordTotal > 0)
            .GroupBy(r => r.Pattern)
            .ToDictionary(g => g.Key, g => (
                Hits:  g.Sum(r => r.KeywordHits),
                Total: g.Sum(r => r.KeywordTotal)));

        Console.WriteLine($"{"pattern",-12} {"hits",6} {"of",6} {"score",10}");
        Console.WriteLine(new string('-', 38));
        foreach (string name in new[] { "Monolithic", "Sequential", "Concurrent" })
        {
            if (!byPattern.TryGetValue(name, out var s)) continue;
            double pct = s.Total == 0 ? 0 : s.Hits * 100.0 / s.Total;
            Console.WriteLine($"{name,-12} {s.Hits,6} {s.Total,6} {pct,9:F1}%");
        }
        Console.WriteLine();
    }

    private static void PrintCostSummary(IEnumerable<TurnResult> results)
    {
        Console.WriteLine("============================================================");
        Console.WriteLine("  COST — total tokens (input + output) per pattern");
        Console.WriteLine("============================================================");
        var byPattern = results
            .GroupBy(r => r.Pattern)
            .ToDictionary(g => g.Key, g => (
                In:  g.Sum(r => r.InputTokens),
                Out: g.Sum(r => r.OutputTokens),
                Turns: g.Sum(r => r.ModelTurns)));

        Console.WriteLine($"{"pattern",-12} {"input",9} {"output",9} {"total",9} {"turns",6}");
        Console.WriteLine(new string('-', 50));
        foreach (string name in new[] { "Monolithic", "Sequential", "Concurrent" })
        {
            if (!byPattern.TryGetValue(name, out var s)) continue;
            Console.WriteLine($"{name,-12} {s.In,9:N0} {s.Out,9:N0} {s.In + s.Out,9:N0} {s.Turns,6}");
        }
        Console.WriteLine();
    }

    private static void PrintLatencySummary(IEnumerable<TurnResult> results)
    {
        Console.WriteLine("============================================================");
        Console.WriteLine("  LATENCY — wall-clock ms (lower = faster end-to-end)");
        Console.WriteLine("============================================================");
        var byPattern = results
            .GroupBy(r => r.Pattern)
            .ToDictionary(g => g.Key, g => (
                Total: g.Sum(r => r.ElapsedMs),
                Avg:   (long)g.Average(r => r.ElapsedMs)));

        Console.WriteLine($"{"pattern",-12} {"total ms",10} {"avg ms",10}");
        Console.WriteLine(new string('-', 36));
        foreach (string name in new[] { "Monolithic", "Sequential", "Concurrent" })
        {
            if (!byPattern.TryGetValue(name, out var s)) continue;
            Console.WriteLine($"{name,-12} {s.Total,10:N0} {s.Avg,10:N0}");
        }
        Console.WriteLine();
        Console.WriteLine("Sequential serializes 3 model calls; Concurrent runs the last");
        Console.WriteLine("two in parallel; Monolithic does it all in one call.");
    }

    private static string Timestamp() => DateTime.Now.ToString("HH:mm:ss.fff");

    private static string Truncate(string s, int max) =>
        s.Length <= max ? s.Replace("\n", " ") : s[..max].Replace("\n", " ") + "…";
}
