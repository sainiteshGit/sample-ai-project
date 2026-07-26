using System.Diagnostics;
using System.Text;
using System.Text.Json;

namespace Lab01;

/// <summary>
/// A deliberately tiny, hand-rolled client for the chat completions endpoint.
///
/// This is the whole "AI integration". Every SDK, every agent framework, every
/// orchestration library in existence is a wrapper around this one HTTP POST.
/// Seeing it at this level once is worth more than a month of tutorials.
/// </summary>
internal sealed class RawModelClient
{
    private static readonly HttpClient Http = new() { Timeout = TimeSpan.FromMinutes(5) };

    private readonly string _url;
    private readonly string _apiKey;

    public RawModelClient(string endpoint, string deployment, string apiVersion, string apiKey)
    {
        _url = $"{endpoint.TrimEnd('/')}/openai/deployments/{deployment}" +
               $"/chat/completions?api-version={apiVersion}";
        _apiKey = apiKey;
    }

    private void ApplyAuth(HttpRequestMessage req) => req.Headers.Add("api-key", _apiKey);

    /// <summary>Builds the request body. This object IS your entire conversation.</summary>
    public static Dictionary<string, object?> BuildBody(
        IEnumerable<Msg> messages,
        int? maxTokens = null,
        double? temperature = null,
        bool stream = false,
        bool includeUsageInStream = true)
    {
        var body = new Dictionary<string, object?>
        {
            ["messages"] = messages.Select(m => new { role = m.Role, content = m.Content }).ToArray(),
        };

        if (maxTokens is not null) body["max_tokens"] = maxTokens;
        if (temperature is not null) body["temperature"] = temperature;

        if (stream)
        {
            body["stream"] = true;
            // Streaming responses omit `usage` unless you ask for it. If you bill
            // or budget on tokens, forgetting this silently loses your telemetry.
            if (includeUsageInStream)
                body["stream_options"] = new { include_usage = true };
        }

        return body;
    }

    /// <summary>One blocking POST. Returns the parsed response and wall-clock time.</summary>
    public async Task<(JsonDocument Json, TimeSpan Elapsed, int RequestBytes)> SendAsync(
        Dictionary<string, object?> body, CancellationToken ct = default)
    {
        var payload = JsonSerializer.Serialize(body);
        using var req = new HttpRequestMessage(HttpMethod.Post, _url)
        {
            Content = new StringContent(payload, Encoding.UTF8, "application/json"),
        };
        ApplyAuth(req);

        var sw = Stopwatch.StartNew();
        using var resp = await Http.SendAsync(req, ct);
        var raw = await resp.Content.ReadAsStringAsync(ct);
        sw.Stop();

        if (!resp.IsSuccessStatusCode)
            throw new HttpRequestException($"HTTP {(int)resp.StatusCode}\n{Trim(raw, 1500)}");

        return (JsonDocument.Parse(raw), sw.Elapsed, Encoding.UTF8.GetByteCount(payload));
    }

    /// <summary>
    /// Streaming POST. Reads Server-Sent Events line by line and records the
    /// arrival time of every chunk, which is what lets us separate TTFT from TPOT.
    /// </summary>
    public async Task<StreamResult> StreamAsync(
        Dictionary<string, object?> body, CancellationToken ct = default)
    {
        var payload = JsonSerializer.Serialize(body);
        using var req = new HttpRequestMessage(HttpMethod.Post, _url)
        {
            Content = new StringContent(payload, Encoding.UTF8, "application/json"),
        };
        ApplyAuth(req);

        var sw = Stopwatch.StartNew();
        using var resp = await Http.SendAsync(req, HttpCompletionOption.ResponseHeadersRead, ct);
        var raw0 = resp.IsSuccessStatusCode ? null : await resp.Content.ReadAsStringAsync(ct);
        if (raw0 is not null)
            throw new HttpRequestException($"HTTP {(int)resp.StatusCode}\n{Trim(raw0, 1500)}");

        await using var stream = await resp.Content.ReadAsStreamAsync(ct);
        using var reader = new StreamReader(stream);

        var text = new StringBuilder();
        var chunks = new List<string>();
        var arrivals = new List<double>();
        TimeSpan? ttft = null;
        Usage? usage = null;
        string? finishReason = null;

        while (await reader.ReadLineAsync(ct) is { } line)
        {
            if (!line.StartsWith("data:", StringComparison.Ordinal)) continue;

            var data = line[5..].Trim();
            if (data == "[DONE]") break;

            using var doc = JsonDocument.Parse(data);
            var root = doc.RootElement;

            if (root.TryGetProperty("usage", out var u) && u.ValueKind == JsonValueKind.Object)
                usage = Usage.From(u);

            if (!root.TryGetProperty("choices", out var choices) || choices.GetArrayLength() == 0)
                continue;

            var choice = choices[0];
            if (choice.TryGetProperty("finish_reason", out var fr) && fr.ValueKind == JsonValueKind.String)
                finishReason = fr.GetString();

            if (!choice.TryGetProperty("delta", out var delta)) continue;
            if (!delta.TryGetProperty("content", out var c) || c.ValueKind != JsonValueKind.String) continue;

            var piece = c.GetString();
            if (string.IsNullOrEmpty(piece)) continue;

            ttft ??= sw.Elapsed;
            arrivals.Add(sw.Elapsed.TotalMilliseconds);
            chunks.Add(piece);
            text.Append(piece);
        }

        sw.Stop();

        return new StreamResult(
            text.ToString(), chunks, arrivals, ttft ?? TimeSpan.Zero,
            sw.Elapsed, usage, finishReason, Encoding.UTF8.GetByteCount(payload));
    }

    private static string Trim(string s, int n) => s.Length <= n ? s : s[..n] + "...";
}

internal readonly record struct Msg(string Role, string Content)
{
    public static Msg System(string c) => new("system", c);
    public static Msg User(string c) => new("user", c);
    public static Msg Assistant(string c) => new("assistant", c);
}

internal sealed record Usage(int PromptTokens, int CompletionTokens, int TotalTokens)
{
    /// <summary>
    /// Tokens the provider served from its prefix cache rather than re-running
    /// prefill on. This is GROUND TRUTH for prefix caching -- unlike wall-clock
    /// timing from a laptop, it cannot be confounded by network noise.
    /// Billed at a fraction of the normal input rate.
    /// </summary>
    public int CachedTokens { get; init; }

    /// <summary>
    /// Server-side timing breakdown, when the provider supplies it (Azure does,
    /// under usage.latency_checkpoint). These are measured INSIDE the service,
    /// so they exclude your network path entirely.
    ///   EngineTtftMs -- real prefill time on the GPU.
    ///   EngineTbtMs  -- real time-between-tokens, i.e. honest TPOT.
    ///   PreInferenceMs -- routing/queueing before the model ever ran.
    /// </summary>
    public double EngineTtftMs { get; init; }
    public double EngineTbtMs { get; init; }
    public double PreInferenceMs { get; init; }
    public bool HasServerTiming => EngineTtftMs > 0 || EngineTbtMs > 0;

    public static Usage From(JsonElement u)
    {
        var usage = new Usage(
            u.TryGetProperty("prompt_tokens", out var p) ? p.GetInt32() : 0,
            u.TryGetProperty("completion_tokens", out var c) ? c.GetInt32() : 0,
            u.TryGetProperty("total_tokens", out var t) ? t.GetInt32() : 0);

        if (u.TryGetProperty("prompt_tokens_details", out var d) &&
            d.TryGetProperty("cached_tokens", out var ct))
            usage = usage with { CachedTokens = ct.GetInt32() };

        if (u.TryGetProperty("latency_checkpoint", out var l))
            usage = usage with
            {
                EngineTtftMs = Num(l, "engine_ttft_ms"),
                EngineTbtMs = Num(l, "engine_tbt_ms"),
                PreInferenceMs = Num(l, "pre_inference_ms"),
            };

        return usage;

        static double Num(JsonElement e, string name) =>
            e.TryGetProperty(name, out var v) && v.TryGetDouble(out var d) ? d : 0;
    }
}

internal sealed record StreamResult(
    string Text,
    List<string> Chunks,
    List<double> ArrivalsMs,
    TimeSpan Ttft,
    TimeSpan Total,
    Usage? Usage,
    string? FinishReason,
    int RequestBytes)
{
    /// <summary>
    /// Mean gap between chunk arrivals -- our measured Time Per Output Token.
    /// Measured from the FIRST chunk onward, so prefill time is excluded.
    /// </summary>
    public double TpotMs => ArrivalsMs.Count < 2
        ? 0
        : (ArrivalsMs[^1] - ArrivalsMs[0]) / (ArrivalsMs.Count - 1);

    /// <summary>
    /// True when the provider coalesced many tokens into one network flush.
    ///
    /// Real decode requires a full forward pass per token -- single-digit to
    /// tens of milliseconds. If most inter-chunk gaps are sub-millisecond, we
    /// are timing our own socket reads, not the GPU, and TPOT is meaningless.
    /// Detecting this matters: the numbers look perfectly plausible either way.
    /// </summary>
    public bool LooksBuffered
    {
        get
        {
            if (ArrivalsMs.Count < 4) return false;
            var nearZero = 0;
            for (var i = 1; i < ArrivalsMs.Count; i++)
                if (ArrivalsMs[i] - ArrivalsMs[i - 1] < 0.5) nearZero++;
            return nearZero > (ArrivalsMs.Count - 1) * 0.6;
        }
    }
}
