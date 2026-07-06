using AcaMcpServer.Tools;

var builder = WebApplication.CreateBuilder(args);

// Register the MCP server + expose it over HTTP (streamable) so it can run in Azure Container Apps.
builder.Services
    .AddMcpServer()
    .WithHttpTransport()
    .WithTools<WeatherTools>()
    .WithTools<StockTools>();

// Container Apps sends traffic to the container on the port defined by $PORT (default 8080).
var port = Environment.GetEnvironmentVariable("PORT") ?? "8080";
builder.WebHost.UseUrls($"http://0.0.0.0:{port}");

var app = builder.Build();

// Small health endpoint so ACA (and you) can verify the container is alive.
app.MapGet("/", () => Results.Ok(new { status = "ok", service = "aca-mcp-server" }));

// MCP endpoint. Clients POST to /mcp; server streams responses back.
app.MapMcp("/mcp");

app.Run();
