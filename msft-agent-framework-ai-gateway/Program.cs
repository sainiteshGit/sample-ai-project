using System.ClientModel;
using System.ClientModel.Primitives;
using System.Diagnostics;
using Azure.AI.OpenAI;
using Microsoft.Extensions.Configuration;
using OpenAI.Chat;

namespace AIGatewaySample;

/// <summary>
/// Demonstrates calling an Azure OpenAI / Microsoft Foundry model deployment
/// through Azure API Management (the "AI Gateway" surface in Foundry).
///
/// Four scenarios:
///   1. Baseline call — show that the SDK works unchanged when the endpoint
///      points at APIM instead of the model.
///   2. Per-team headers — emit x-team-id so an llm-emit-token-metric policy
///      can attribute tokens to "alpha" vs "beta".
///   3. Burst test — fire N requests quickly so an llm-token-limit policy
///      can return 429s. We surface Retry-After + remaining-tokens headers.
///   4. Cache check — send the SAME prompt twice; if the API has
///      llm-semantic-cache-* policies, the second call should be cheaper /
///      faster (no completion tokens).
///
/// You point this app at the *gateway* URL, not the Foundry URL:
///   https://&lt;your-apim&gt;.azure-api.net/openai
/// and supply an APIM subscription key.
/// </summary>
class Program
{
    static async Task Main(string[] args)
    {
        var config = new ConfigurationBuilder()
            .SetBasePath(Directory.GetCurrentDirectory())
            .AddJsonFile("appsettings.json", optional: true)
            .AddJsonFile("appsettings.Development.json", optional: true)
            .Build();

        var endpoint = config["Gateway:Endpoint"];
        var apiKey = config["Gateway:ApiKey"];
        var deployment = config["Gateway:DeploymentName"] ?? "gpt-4o-mini";
        var teamA = config["Demo:TeamA"] ?? "alpha";
        var teamB = config["Demo:TeamB"] ?? "beta";
        var burstCount = config.GetValue<int>("Demo:BurstCount", 12);
        var prompts = config.GetSection("Demo:Prompts").Get<string[]>() ?? new[]
        {
            "Summarize the role of an AI gateway in 2 sentences."
        };

        if (string.IsNullOrWhiteSpace(endpoint) || endpoint.Contains("your-apim"))
        {
            Console.WriteLine("Set Gateway:Endpoint in appsettings.Development.json to your APIM URL.");
            Console.WriteLine("Copy appsettings.Development.json.template and fill it in.");
            return;
        }

        Console.WriteLine("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        Console.WriteLine("  Microsoft Foundry — AI Gateway Demo");
        Console.WriteLine("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        Console.WriteLine($"Gateway:    {endpoint}");
        Console.WriteLine($"Deployment: {deployment}");
        Console.WriteLine();

        // ── Scenario 1: baseline call through gateway ──
        await Scenario1_Baseline(endpoint!, apiKey!, deployment, prompts[0]);

        // ── Scenario 2: per-team attribution via x-team-id header ──
        await Scenario2_PerTeamMetrics(endpoint!, apiKey!, deployment, prompts, teamA, teamB);

        // ── Scenario 4: same prompt twice (semantic-cache policy) ──
        await Scenario4_CacheRepeat(endpoint!, apiKey!, deployment, prompts[0]);

        // ── Scenario 3: burst until 429 (token-limit policy) ──
        // Run last because it intentionally exhausts the TPM bucket.
        // Wait 65s first so the bucket is full before we try to deplete it.
        Console.WriteLine("Waiting 65s for the per-minute TPM bucket to refill before the burst test...");
        await Task.Delay(TimeSpan.FromSeconds(65));
        await Scenario3_BurstUntilThrottled(endpoint!, apiKey!, deployment, prompts[0], burstCount);

        Console.WriteLine();
        Console.WriteLine("Done. Now check APIM → Monitoring → Metrics (Requests, Failed Requests),");
        Console.WriteLine("and Application Insights for the llm-emit-token-metric values.");
    }

    // ─────────────────────────────────────────────────────────
    // Helpers
    // ─────────────────────────────────────────────────────────

    /// <summary>
    /// Build an AzureOpenAIClient that routes through APIM and stamps a custom
    /// header (x-team-id, x-app-id) onto every outbound request. The header is
    /// what an llm-emit-token-metric or llm-token-limit policy will key on.
    /// </summary>
    static AzureOpenAIClient BuildClient(string endpoint, string apiKey, string? teamId = null, string appId = "ai-gateway-sample", bool disableRetries = false)
    {
        var options = new AzureOpenAIClientOptions();

        // Attach a per-request header policy. Runs on every call from this client.
        options.AddPolicy(new HeaderInjectionPolicy(new Dictionary<string, string>
        {
            ["x-team-id"] = teamId ?? "default",
            ["x-app-id"] = appId
        }), PipelinePosition.PerCall);

        // For the throttle demo we want 429s to surface immediately instead of
        // being swallowed by the SDK's exponential-backoff retry. The SDK's
        // default policy treats 429 as transient and waits Retry-After (often
        // 30-60s) before re-issuing — which makes the throttle invisible.
        if (disableRetries)
        {
            options.RetryPolicy = new ClientRetryPolicy(maxRetries: 0);
        }

        // APIM expects the subscription key in Ocp-Apim-Subscription-Key OR api-key.
        // The Azure OpenAI SDK already sends api-key, which APIM accepts as the
        // subscription key when the API is configured with that header name —
        // which is the default for AI-Gateway-imported APIs in Foundry.
        return new AzureOpenAIClient(new Uri(endpoint), new ApiKeyCredential(apiKey), options);
    }

    static async Task Scenario1_Baseline(string endpoint, string apiKey, string deployment, string prompt)
    {
        Console.WriteLine("━━ Scenario 1: Baseline call through the gateway ━━");
        var client = BuildClient(endpoint, apiKey, disableRetries: true);
        var chat = client.GetChatClient(deployment);

        var sw = Stopwatch.StartNew();
        try
        {
            var resp = await chat.CompleteChatAsync(new ChatMessage[] { new UserChatMessage(prompt) });
            sw.Stop();
            var usage = resp.Value.Usage;
            Console.WriteLine($"  ok   {sw.ElapsedMilliseconds,5} ms   prompt={usage.InputTokenCount}  completion={usage.OutputTokenCount}");
            Console.WriteLine($"  reply: {Truncate(resp.Value.Content[0].Text, 120)}");
        }
        catch (ClientResultException ex)
        {
            sw.Stop();
            Console.WriteLine($"  {ex.Status} {sw.ElapsedMilliseconds,5} ms   {ex.Message.Split('\n')[0]}");
        }
        Console.WriteLine();
    }

    static async Task Scenario2_PerTeamMetrics(string endpoint, string apiKey, string deployment, string[] prompts, string teamA, string teamB)
    {
        Console.WriteLine("━━ Scenario 2: Per-team token metrics (x-team-id) ━━");
        Console.WriteLine($"  Sending {prompts.Length} prompts as team='{teamA}', then {prompts.Length} as team='{teamB}'.");

        await Send(teamA);
        await Send(teamB);

        Console.WriteLine("  → In Application Insights, run:");
        Console.WriteLine("      customMetrics");
        Console.WriteLine("      | where name == \"Total Tokens\"");
        Console.WriteLine("      | extend Team = tostring(customDimensions[\"Team\"])");
        Console.WriteLine("      | summarize sum(value) by Team");
        Console.WriteLine();

        async Task Send(string team)
        {
            var client = BuildClient(endpoint, apiKey, teamId: team, disableRetries: true);
            var chat = client.GetChatClient(deployment);
            int total = 0;
            int throttled = 0;
            foreach (var p in prompts)
            {
                try
                {
                    var resp = await chat.CompleteChatAsync(new ChatMessage[] { new UserChatMessage(p) });
                    total += resp.Value.Usage.TotalTokenCount;
                }
                catch (ClientResultException ex) when (ex.Status == 429)
                {
                    throttled++;
                }
            }
            Console.WriteLine($"  team={team,-6} ok tokens: {total,4}   throttled prompts: {throttled}");
        }
    }

    static async Task Scenario3_BurstUntilThrottled(string endpoint, string apiKey, string deployment, string prompt, int burstCount)
    {
        Console.WriteLine($"━━ Scenario 3: Send {burstCount} sequential requests until throttled ━━");
        Console.WriteLine("  (sequential, not parallel — concurrent requests leak past llm-token-limit");
        Console.WriteLine("   per the docs, because token counts are only known after responses arrive)");

        // Use a raw HttpClient so 429 responses surface immediately. The Azure
        // OpenAI SDK has built-in retry-on-429 + Retry-After honouring, which
        // hides the throttle behind 30–60s waits.
        using var http = new HttpClient { Timeout = TimeSpan.FromSeconds(15) };
        var url = $"{endpoint.TrimEnd('/')}/openai/deployments/{deployment}/chat/completions?api-version=2024-10-21";
        var body = System.Text.Json.JsonSerializer.Serialize(new
        {
            messages = new[] { new { role = "user", content = prompt } },
            max_completion_tokens = 64
        });

        int ok = 0, throttled = 0, other = 0, cumulativeTokens = 0;
        for (int i = 0; i < burstCount; i++)
        {
            var sw = Stopwatch.StartNew();
            using var req = new HttpRequestMessage(HttpMethod.Post, url)
            {
                Content = new StringContent(body, System.Text.Encoding.UTF8, "application/json")
            };
            req.Headers.Add("api-key", apiKey);
            req.Headers.Add("x-team-id", "burst-team");
            req.Headers.Add("x-app-id", "ai-gateway-sample");

            int status;
            string? retryAfter = null;
            int totalTokens = 0;
            try
            {
                using var resp = await http.SendAsync(req);
                sw.Stop();
                status = (int)resp.StatusCode;
                retryAfter = resp.Headers.RetryAfter?.ToString();
                if (resp.IsSuccessStatusCode)
                {
                    var text = await resp.Content.ReadAsStringAsync();
                    using var doc = System.Text.Json.JsonDocument.Parse(text);
                    if (doc.RootElement.TryGetProperty("usage", out var usage) &&
                        usage.TryGetProperty("total_tokens", out var t))
                    {
                        totalTokens = t.GetInt32();
                        cumulativeTokens += totalTokens;
                    }
                }
            }
            catch (Exception ex)
            {
                sw.Stop();
                status = -1;
                retryAfter = ex.GetType().Name;
            }

            if (status == 200) ok++;
            else if (status == 429) throttled++;
            else other++;

            var label = status switch
            {
                200 => "ok ",
                429 => "429",
                -1  => "ERR",
                _ => status.ToString()
            };
            Console.WriteLine($"  #{i:00}  {label}  {sw.ElapsedMilliseconds,5} ms   tokens={totalTokens,4}   cumulative={cumulativeTokens,5}   retry-after={retryAfter ?? "-"}");

            // Once we hit the throttle, send 2-3 more to confirm it sticks, then stop.
            if (throttled >= 3) break;
        }

        Console.WriteLine($"  → ok={ok}  throttled={throttled}  other={other}  cumulative tokens={cumulativeTokens}");
        if (throttled == 0)
        {
            Console.WriteLine("  (No 429s? Either no llm-token-limit policy is attached, the limit is");
            Console.WriteLine("   higher than the cumulative tokens above, or the API subscription key");
            Console.WriteLine("   isn't keyed to a project that has a TPM limit configured.)");
        }
        Console.WriteLine();
    }

    static async Task Scenario4_CacheRepeat(string endpoint, string apiKey, string deployment, string prompt)
    {
        Console.WriteLine("━━ Scenario 4: Same prompt twice (semantic cache check) ━━");
        var client = BuildClient(endpoint, apiKey, teamId: "cache-test", disableRetries: true);
        var chat = client.GetChatClient(deployment);

        for (int attempt = 1; attempt <= 2; attempt++)
        {
            var sw = Stopwatch.StartNew();
            try
            {
                var resp = await chat.CompleteChatAsync(new ChatMessage[] { new UserChatMessage(prompt) });
                sw.Stop();
                var u = resp.Value.Usage;
                Console.WriteLine($"  attempt {attempt}: {sw.ElapsedMilliseconds,5} ms   prompt={u.InputTokenCount}  completion={u.OutputTokenCount}  total={u.TotalTokenCount}");
            }
            catch (ClientResultException ex)
            {
                sw.Stop();
                Console.WriteLine($"  attempt {attempt}: {ex.Status} {sw.ElapsedMilliseconds,5} ms   throttled");
            }
        }
        Console.WriteLine("  → If llm-semantic-cache-{lookup,store} is configured, attempt 2 should be");
        Console.WriteLine("    visibly faster and report 0 completion tokens (cached body).");
        Console.WriteLine();
    }

    static string Truncate(string s, int n) => s.Length <= n ? s : s[..n] + "…";
}

/// <summary>
/// Pipeline policy that injects static headers onto every request. Used to send
/// x-team-id / x-app-id so APIM policies (llm-token-limit counter-key,
/// llm-emit-token-metric dimension) can read them.
/// </summary>
internal sealed class HeaderInjectionPolicy : PipelinePolicy
{
    private readonly IReadOnlyDictionary<string, string> _headers;

    public HeaderInjectionPolicy(IReadOnlyDictionary<string, string> headers) => _headers = headers;

    public override void Process(PipelineMessage message, IReadOnlyList<PipelinePolicy> pipeline, int currentIndex)
    {
        Apply(message);
        if (currentIndex < pipeline.Count - 1)
            pipeline[currentIndex + 1].Process(message, pipeline, currentIndex + 1);
    }

    public override async ValueTask ProcessAsync(PipelineMessage message, IReadOnlyList<PipelinePolicy> pipeline, int currentIndex)
    {
        Apply(message);
        if (currentIndex < pipeline.Count - 1)
            await pipeline[currentIndex + 1].ProcessAsync(message, pipeline, currentIndex + 1).ConfigureAwait(false);
    }

    private void Apply(PipelineMessage message)
    {
        foreach (var (k, v) in _headers)
        {
            message.Request.Headers.Set(k, v);
        }
    }
}
