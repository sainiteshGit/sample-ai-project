using System.ClientModel;
using System.Diagnostics;
using Azure.AI.OpenAI;
using Azure.Identity;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using Microsoft.Extensions.Configuration;

namespace SkillsBenchmark;

/// <summary>
/// Two-way benchmark comparing two ways of giving an agent the SAME .md content:
///
///   A) RawPromptAgent — every SKILL.md file is read with File.ReadAllText,
///                       concatenated into one big string, and shoved into the
///                       agent's system Instructions. Sent in full on every turn.
///                       No tools, no skills provider — just raw text in the prompt.
///
///   B) SkillsAgent    — the same SKILL.md files are exposed via
///                       FileAgentSkillsProvider (progressive disclosure).
///                       Only short skill DESCRIPTIONS sit in the prompt. The
///                       model decides which skill is relevant and calls
///                       load_skill to fetch that one body on demand.
///
/// Two questions answered:
///   QUALITY (RawPrompt vs Skills): does either approach drop policy fidelity?
///                                  Measured by counting policy-specific keywords
///                                  (e.g. "$75", "P1", "30 days") in each answer.
///   COST    (RawPrompt vs Skills): how many input tokens does progressive
///                                  disclosure save for the same answer quality?
/// </summary>
internal class Program
{
    private record TurnResult(
        string AgentName,
        string PromptLabel,
        long InputTokens,
        long OutputTokens,
        long TotalTokens,
        long ElapsedMs,
        int KeywordHits,
        int KeywordTotal,
        string FullResponse);

    static async Task Main()
    {
        IConfiguration config = new ConfigurationBuilder()
            .SetBasePath(Directory.GetCurrentDirectory())
            .AddJsonFile("appsettings.json", optional: true)
            .AddJsonFile("appsettings.Development.json", optional: true)
            .Build();

        string? endpoint   = config["AzureOpenAI:Endpoint"];
        string? apiKey     = config["AzureOpenAI:ApiKey"];
        string  deployment = config["AzureOpenAI:DeploymentName"] ?? "gpt-4o-mini";

        if (string.IsNullOrWhiteSpace(endpoint))
        {
            Console.Error.WriteLine(
                "Set AzureOpenAI:Endpoint in appsettings.Development.json " +
                "(copy appsettings.Development.json.template).");
            return;
        }

        AzureOpenAIClient openAI = string.IsNullOrWhiteSpace(apiKey)
            ? new AzureOpenAIClient(new Uri(endpoint), new DefaultAzureCredential())
            : new AzureOpenAIClient(new Uri(endpoint), new ApiKeyCredential(apiKey));

        string skillsDir = Path.Combine(AppContext.BaseDirectory, "skills");
        string rawPrompt = RawPromptAgentBuilder.LoadAllSkillBodies(skillsDir);

        Console.WriteLine("============================================================");
        Console.WriteLine("  Skills .md files: do they help, and at what cost?");
        Console.WriteLine("============================================================");
        Console.WriteLine($"Model                : {deployment}");
        Console.WriteLine($"Skills directory     : {skillsDir}");
        Console.WriteLine($"RawPrompt size       : {rawPrompt.Length:N0} chars (~{rawPrompt.Length / 4:N0} tokens, rough)");
        Console.WriteLine();

        var agents = new (string Name, AIAgent Agent)[]
        {
            ("RawPrompt", RawPromptAgentBuilder.Build(openAI, deployment, skillsDir)),
            ("Skills",    SkillsAgentBuilder.Build(openAI,   deployment, skillsDir)),
        };

        var results = new List<TurnResult>();

        foreach (var p in Prompts.All)
        {
            Console.WriteLine($"── Prompt: {p.Label} ──");
            Console.WriteLine($"   {Truncate(p.Text, 110)}");
            if (p.ExpectedKeywords.Length > 0)
            {
                Console.WriteLine($"   expected keywords: [{string.Join(", ", p.ExpectedKeywords)}]");
            }

            foreach (var (name, agent) in agents)
            {
                var r = await RunOnceAsync(name, agent, p);
                results.Add(r);
                string score = r.KeywordTotal == 0 ? "n/a" : $"{r.KeywordHits}/{r.KeywordTotal}";
                Console.WriteLine($"   {name,-9}: in={r.InputTokens,6}  out={r.OutputTokens,5}  " +
                                  $"total={r.TotalTokens,6}  {r.ElapsedMs,5}ms  grounding={score}");
            }

            // Print both responses side-by-side so quality can be eyeballed
            // (keyword grounding is necessary but not sufficient).
            Console.WriteLine();
            foreach (var r in results.Where(x => x.PromptLabel == p.Label))
            {
                Console.WriteLine($"   --- {r.AgentName} response ---");
                foreach (string line in r.FullResponse.Split('\n'))
                {
                    Console.WriteLine($"   | {line}");
                }
            }
            Console.WriteLine();
        }

        PrintQualitySummary(results);
        PrintLatencySummary(results);
        PrintCostSummary(results);
    }

    private static async Task<TurnResult> RunOnceAsync(string agentName, AIAgent agent, Prompts.TestCase prompt)
    {
        Console.WriteLine($"   [{Timestamp()}] -> {agentName,-9} calling model...");
        var sw = Stopwatch.StartNew();
        AgentResponse response;
        try
        {
            response = await agent.RunAsync(prompt.Text);
        }
        catch (Exception ex)
        {
            sw.Stop();
            Console.Error.WriteLine($"   [{Timestamp()}] !! {agentName} failed after {sw.ElapsedMilliseconds}ms: {ex.Message}");
            return new TurnResult(agentName, prompt.Label, 0, 0, 0, sw.ElapsedMilliseconds,
                0, prompt.ExpectedKeywords.Length, $"<error: {ex.Message}>");
        }
        sw.Stop();

        long inTok = 0, outTok = 0, totTok = 0;
        int modelTurns = 0;
        foreach (object? raw in EnumerateRawResponses(response))
        {
            if (raw is ChatResponse cr)
            {
                modelTurns++;
                if (cr.Usage is { } u)
                {
                    inTok  += u.InputTokenCount  ?? 0;
                    outTok += u.OutputTokenCount ?? 0;
                    totTok += u.TotalTokenCount  ?? 0;
                }
            }
        }

        string text = response.Text ?? string.Empty;
        var (hits, total) = Prompts.Score(prompt, text);

        Console.WriteLine($"   [{Timestamp()}] <- {agentName,-9} done in {sw.ElapsedMilliseconds,5}ms " +
                          $"({modelTurns} model turn{(modelTurns == 1 ? "" : "s")})");

        return new TurnResult(
            agentName,
            prompt.Label,
            inTok,
            outTok,
            totTok == 0 ? inTok + outTok : totTok,
            sw.ElapsedMilliseconds,
            hits,
            total,
            text);
    }

    private static string Timestamp() => DateTime.Now.ToString("HH:mm:ss.fff");

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

    private static void PrintQualitySummary(IEnumerable<TurnResult> results)
    {
        Console.WriteLine("============================================================");
        Console.WriteLine("  QUALITY — keyword grounding (higher = better policy fidelity)");
        Console.WriteLine("============================================================");

        var byAgent = results
            .Where(r => r.KeywordTotal > 0)
            .GroupBy(r => r.AgentName)
            .ToDictionary(g => g.Key, g => (
                Hits:  g.Sum(r => r.KeywordHits),
                Total: g.Sum(r => r.KeywordTotal)));

        Console.WriteLine($"{"agent",-10} {"hits",6} {"of",6} {"score",10}");
        Console.WriteLine(new string('-', 36));
        foreach (string name in new[] { "RawPrompt", "Skills" })
        {
            if (!byAgent.TryGetValue(name, out var s)) continue;
            double pct = s.Total == 0 ? 0 : (s.Hits * 100.0 / s.Total);
            Console.WriteLine($"{name,-10} {s.Hits,6} {s.Total,6} {pct,9:F1}%");
        }
        Console.WriteLine();
    }

    private static void PrintLatencySummary(IEnumerable<TurnResult> results)
    {
        Console.WriteLine("============================================================");
        Console.WriteLine("  LATENCY — wall-clock ms per prompt (lower = faster)");
        Console.WriteLine("============================================================");

        var byPrompt = results
            .GroupBy(r => r.PromptLabel)
            .Select(g => new
            {
                Label     = g.Key,
                RawPrompt = g.FirstOrDefault(r => r.AgentName == "RawPrompt")?.ElapsedMs ?? 0,
                Skills    = g.FirstOrDefault(r => r.AgentName == "Skills")?.ElapsedMs    ?? 0,
            })
            .ToList();

        Console.WriteLine($"{"prompt",-22} {"RawPrompt",10} {"Skills",10} {"diff",10}");
        Console.WriteLine(new string('-', 56));
        long totRaw = 0, totSk = 0;
        foreach (var row in byPrompt)
        {
            totRaw += row.RawPrompt; totSk += row.Skills;
            long diff = row.Skills - row.RawPrompt; // positive = Skills slower
            Console.WriteLine($"{row.Label,-22} {row.RawPrompt,10:N0} " +
                              $"{row.Skills,10:N0} {diff,+10:N0}");
        }
        Console.WriteLine(new string('-', 56));
        Console.WriteLine($"{"TOTAL",-22} {totRaw,10:N0} {totSk,10:N0} {totSk - totRaw,+10:N0}");
        Console.WriteLine($"{"AVG / prompt",-22} {totRaw / byPrompt.Count,10:N0} " +
                          $"{totSk / byPrompt.Count,10:N0} {(totSk - totRaw) / byPrompt.Count,+10:N0}");
        Console.WriteLine();
        Console.WriteLine("Skills is typically slower per turn (file read + provider overhead),");
        Console.WriteLine("but that overhead amortizes across multi-turn sessions while the");
        Console.WriteLine("token savings repeat every turn.");
        Console.WriteLine();
    }

    private static void PrintCostSummary(IEnumerable<TurnResult> results)
    {
        Console.WriteLine("============================================================");
        Console.WriteLine("  COST — input tokens per prompt (lower = cheaper)");
        Console.WriteLine("============================================================");

        var byPrompt = results
            .GroupBy(r => r.PromptLabel)
            .Select(g => new
            {
                Label     = g.Key,
                RawPrompt = g.FirstOrDefault(r => r.AgentName == "RawPrompt")?.InputTokens ?? 0,
                Skills    = g.FirstOrDefault(r => r.AgentName == "Skills")?.InputTokens    ?? 0,
            })
            .ToList();

        Console.WriteLine($"{"prompt",-22} {"RawPrompt",10} {"Skills",10} " +
                          $"{"Sk vs Raw",10} {"saved %",10}");
        Console.WriteLine(new string('-', 72));

        long totRaw = 0, totSk = 0;
        foreach (var row in byPrompt)
        {
            totRaw += row.RawPrompt; totSk += row.Skills;
            long diff = row.RawPrompt - row.Skills;
            string pct = row.RawPrompt > 0 ? $"{diff * 100.0 / row.RawPrompt:F1}%" : "n/a";
            Console.WriteLine($"{row.Label,-22} {row.RawPrompt,10:N0} " +
                              $"{row.Skills,10:N0} {diff,10:N0} {pct,10}");
        }

        Console.WriteLine(new string('-', 72));
        long totalDiff = totRaw - totSk;
        string totalPct = totRaw > 0 ? $"{totalDiff * 100.0 / totRaw:F1}%" : "n/a";
        Console.WriteLine($"{"TOTAL",-22} {totRaw,10:N0} {totSk,10:N0} " +
                          $"{totalDiff,10:N0} {totalPct,10}");
        Console.WriteLine();
        Console.WriteLine("RawPrompt = every SKILL.md File.ReadAllText'd and concatenated into the");
        Console.WriteLine("            agent's system Instructions string. Sent on every turn.");
        Console.WriteLine("Skills    = same files exposed via FileAgentSkillsProvider; only short");
        Console.WriteLine("            descriptions in prompt, full body fetched lazily via load_skill.");
    }

    private static string Truncate(string s, int max) =>
        s.Length <= max ? s.Replace("\n", " ") : s[..max].Replace("\n", " ") + "…";
}
