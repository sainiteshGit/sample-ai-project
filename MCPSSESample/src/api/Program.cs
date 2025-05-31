using RemoteMcp.Tools;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddMcpServer()
    .WithHttpTransport()
    .WithTools<SampleSSETransportTool>();

builder.Services.AddHttpContextAccessor();

var app = builder.Build();

app.MapMcp();

app.Run();
