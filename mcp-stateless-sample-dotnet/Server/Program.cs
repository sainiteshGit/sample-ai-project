// MCP Server using the official ModelContextProtocol C# SDK (v1.3.0).
//
// Exposes two endpoints to make the protocol shift visible:
//   * /mcp        -> the SDK's Streamable HTTP handler (MCP 2025-11-25,
//                    requires Mcp-Session-Id after initialize)
//   * /stateless  -> a hand-rolled, sessionless POST endpoint that mirrors
//                    what 2026-07-28 enables: any pod can serve any request
//                    as long as the application carries its own handle.
//
// Both endpoints share the same BasketTools and BasketStore. When the
// SHARED_STORE_PATH env var is set, the store is backed by a JSON file so
// all pods see the same baskets — that's the "Redis/Cosmos" stand-in.

using System.Text.Json;
using McpStatelessSample.Server.Tools;

var instanceId = Environment.GetEnvironmentVariable("INSTANCE_ID")
                 ?? $"srv-{Guid.NewGuid():N}"[..6];

var builder = WebApplication.CreateBuilder(args);

builder.Services
    .AddMcpServer(options =>
    {
        options.ServerInfo = new() { Name = $"stateless-sample-{instanceId}", Version = "1.0.0" };
    })
    .WithHttpTransport()
    .WithToolsFromAssembly();

builder.Services.AddSingleton<BasketStore>();
builder.Services.AddSingleton<BasketTools>();

builder.Services.AddLogging(b =>
    b.AddSimpleConsole(o => { o.SingleLine = true; o.IncludeScopes = false; }));

var app = builder.Build();

// --- Today's protocol (2025-11-25) -----------------------------------------
// The SDK enforces Mcp-Session-Id after the initialize handshake. Any LB that
// doesn't pin clients to a single pod will see "Session not found" errors.
app.MapMcp();

// --- Tomorrow's protocol (2026-07-28-style) --------------------------------
// No session header. No initialize. The model-visible handle (basket_id) is
// the only thing that ties calls together. Any pod can serve any request.
app.MapPost("/stateless/tools/call", async (HttpContext ctx, BasketTools tools) =>
{
    using var doc = await JsonDocument.ParseAsync(ctx.Request.Body);
    var root = doc.RootElement;
    var name = root.GetProperty("name").GetString();
    var args = root.TryGetProperty("arguments", out var a) ? a : default;

    object? result = name switch
    {
        "create_basket" => tools.CreateBasket(
            args.TryGetProperty("owner", out var o) ? o.GetString() ?? "anonymous" : "anonymous"),
        "add_item" => tools.AddItem(
            args.GetProperty("basket_id").GetString()!,
            args.GetProperty("sku").GetString()!,
            args.TryGetProperty("qty", out var q) ? q.GetInt32() : 1),
        "view_basket" => tools.ViewBasket(args.GetProperty("basket_id").GetString()!),
        _ => null,
    };

    if (result is null)
    {
        ctx.Response.StatusCode = 400;
        await ctx.Response.WriteAsync($"Unknown tool: {name}");
        return;
    }

    ctx.Response.ContentType = "application/json";
    await JsonSerializer.SerializeAsync(ctx.Response.Body, result);
});

app.MapGet("/whoami", (BasketStore store) => new
{
    instance = instanceId,
    store = store.IsShared ? "shared (file)" : "in-memory",
});

var port = Environment.GetEnvironmentVariable("PORT") ?? "8000";
app.Urls.Add($"http://127.0.0.1:{port}");

Console.WriteLine($"Instance {instanceId} listening on http://127.0.0.1:{port}");
app.Run();
