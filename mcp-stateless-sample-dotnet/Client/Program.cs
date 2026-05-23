// MCP Client using the official ModelContextProtocol C# SDK (v1.3.0).
//
// Demonstrates two things end-to-end:
//   1. Idiomatic SDK usage — McpClient + ListToolsAsync + CallToolAsync.
//   2. The *explicit-handle* pattern — we thread a basket_id across multiple
//      tool calls. This is the pattern that becomes mandatory in the
//      2026-07-28 release candidate.

using System.Text.Json;
using ModelContextProtocol.Client;
using ModelContextProtocol.Protocol;

var serverUrl = args.Length > 0 ? args[0] : "http://127.0.0.1:8001";
Console.WriteLine($"Connecting to {serverUrl} ...");

// Today's SDK (1.3.0) speaks MCP 2025-11-25 — Streamable HTTP with an
// initialize handshake and an Mcp-Session-Id header. None of that is visible
// from this code — the SDK hides it. See ../WireDiff for the raw bytes.
var transport = new HttpClientTransport(new HttpClientTransportOptions
{
    Endpoint = new Uri(serverUrl),
});

await using var client = await McpClient.CreateAsync(transport);

Banner("1. List tools");
var tools = await client.ListToolsAsync();
foreach (var t in tools)
    Console.WriteLine($"  - {t.Name}: {t.Description}");

Banner("2. Explicit-handle pattern — create_basket -> add_item -> view_basket");

var created = await client.CallToolAsync("create_basket",
    new Dictionary<string, object?> { ["owner"] = "alice" });
var createdJson = ExtractStructured(created);
var basketId = createdJson.GetProperty("basket_id").GetString()!;
Console.WriteLine($"  basket {basketId} created on {createdJson.GetProperty("created_by_instance")}");

foreach (var sku in new[] { "book-001", "mug-042", "pen-007" })
{
    var added = await client.CallToolAsync("add_item",
        new Dictionary<string, object?>
        {
            ["basket_id"] = basketId,
            ["sku"] = sku,
        });
    var addedJson = ExtractStructured(added);
    Console.WriteLine($"  added {sku} via {addedJson.GetProperty("handled_by_instance")}");
}

var view = await client.CallToolAsync("view_basket",
    new Dictionary<string, object?> { ["basket_id"] = basketId });
var viewJson = ExtractStructured(view);
var itemCount = viewJson.GetProperty("items").GetArrayLength();
Console.WriteLine($"  final view: {itemCount} items, served by {viewJson.GetProperty("handled_by_instance")}");

Console.WriteLine("\nDone.\n");

static void Banner(string title)
{
    Console.WriteLine();
    Console.WriteLine(new string('=', 72));
    Console.WriteLine($"  {title}");
    Console.WriteLine(new string('=', 72));
}

// Tools return structuredContent in SDK 1.3.0; we surface it as JsonElement
// to keep the demo schema-flexible.
static JsonElement ExtractStructured(CallToolResult result)
{
    if (result.StructuredContent is JsonElement el) return el;
    if (result.StructuredContent is not null)
        return JsonSerializer.SerializeToElement(result.StructuredContent);

    var text = result.Content.OfType<TextContentBlock>().FirstOrDefault()?.Text
               ?? throw new InvalidOperationException("Tool returned no content.");
    return JsonDocument.Parse(text).RootElement;
}
