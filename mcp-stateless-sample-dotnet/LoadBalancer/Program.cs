// Round-robin reverse proxy that fans /mcp (and /stateless) requests across
// two backend pods. Demonstrates what a real load balancer does when nothing
// pins requests to a specific pod.
//
// Purpose: prove that under MCP 2025-11-25, transport-level session ids
// (Mcp-Session-Id) force sticky routing — a naive round-robin LB will break
// the SDK client on the second request.

var backends = new[] { "http://127.0.0.1:8001", "http://127.0.0.1:8002" };
var counter = 0L;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddHttpClient("backend").ConfigurePrimaryHttpMessageHandler(() =>
    new SocketsHttpHandler { AllowAutoRedirect = false, UseCookies = false });
builder.Services.AddLogging(b =>
    b.AddSimpleConsole(o => { o.SingleLine = true; o.IncludeScopes = false; }));

var app = builder.Build();

app.Map("/{**path}", async (HttpContext ctx, IHttpClientFactory http) =>
{
    var idx = (int)(Interlocked.Increment(ref counter) % backends.Length);
    var target = backends[idx];
    var label = idx == 0 ? "A" : "B";

    var req = new HttpRequestMessage(new HttpMethod(ctx.Request.Method),
        target + ctx.Request.Path + ctx.Request.QueryString);

    if (ctx.Request.ContentLength > 0 || ctx.Request.Method is "POST" or "PUT" or "PATCH")
    {
        var ms = new MemoryStream();
        await ctx.Request.Body.CopyToAsync(ms);
        ms.Position = 0;
        req.Content = new StreamContent(ms);
        foreach (var h in ctx.Request.Headers)
        {
            if (h.Key.StartsWith("Content-", StringComparison.OrdinalIgnoreCase))
                req.Content.Headers.TryAddWithoutValidation(h.Key, h.Value.ToArray());
        }
    }

    foreach (var h in ctx.Request.Headers)
    {
        if (h.Key.StartsWith("Content-", StringComparison.OrdinalIgnoreCase)) continue;
        if (string.Equals(h.Key, "Host", StringComparison.OrdinalIgnoreCase)) continue;
        req.Headers.TryAddWithoutValidation(h.Key, h.Value.ToArray());
    }

    Console.WriteLine($"[LB] {ctx.Request.Method} {ctx.Request.Path} -> pod {label} ({target})");

    var client = http.CreateClient("backend");
    using var upstream = await client.SendAsync(req, HttpCompletionOption.ResponseHeadersRead, ctx.RequestAborted);

    ctx.Response.StatusCode = (int)upstream.StatusCode;
    foreach (var h in upstream.Headers) ctx.Response.Headers[h.Key] = h.Value.ToArray();
    foreach (var h in upstream.Content.Headers) ctx.Response.Headers[h.Key] = h.Value.ToArray();
    ctx.Response.Headers.Remove("transfer-encoding");

    await upstream.Content.CopyToAsync(ctx.Response.Body, ctx.RequestAborted);
});

var port = Environment.GetEnvironmentVariable("PORT") ?? "8000";
app.Urls.Add($"http://127.0.0.1:{port}");

Console.WriteLine($"[LB] Round-robin reverse proxy on http://127.0.0.1:{port}");
Console.WriteLine($"[LB] Backends: {string.Join(", ", backends)}");
app.Run();
