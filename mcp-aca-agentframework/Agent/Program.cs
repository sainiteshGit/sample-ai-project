using System.ClientModel;
using Azure.AI.OpenAI;
using Azure.Identity;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using Microsoft.Extensions.Configuration;
using ModelContextProtocol.Client;

namespace AcaMcpAgent;

/// <summary>
/// A tiny console agent built with the Microsoft Agent Framework
/// (Microsoft.Agents.AI) that connects to our MCP server over HTTP
/// and lets the LLM call its tools (GetWeather, GetStockPrice).
///
/// The MCP server can be running locally OR in Azure Container Apps —
/// this code doesn't care, it just needs a URL.
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

        var endpoint       = config["AzureOpenAI:Endpoint"];
        var apiKey         = config["AzureOpenAI:ApiKey"];
        var deploymentName = config["AzureOpenAI:DeploymentName"] ?? "gpt-4o-mini";
        var mcpServerUrl   = args.Length > 0 ? args[0] : config["Mcp:ServerUrl"] ?? "http://localhost:8080/mcp";

        if (string.IsNullOrWhiteSpace(endpoint))
        {
            Console.WriteLine("Set AzureOpenAI:Endpoint in appsettings.Development.json (see the template).");
            return;
        }

        Console.WriteLine("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        Console.WriteLine("  MCP + Microsoft Agent Framework demo    ");
        Console.WriteLine("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        Console.WriteLine($"  MCP server:  {mcpServerUrl}");
        Console.WriteLine($"  Model:       {deploymentName}");
        Console.WriteLine();

        // 1) Connect to the MCP server over HTTP (Streamable HTTP transport).
        var transport = new HttpClientTransport(new HttpClientTransportOptions
        {
            Endpoint = new Uri(mcpServerUrl),
        });
        await using var mcpClient = await McpClient.CreateAsync(transport);

        // 2) Discover the tools the server exposes. These implement AIFunction,
        //    so the Agent Framework can call them directly.
        var mcpTools = await mcpClient.ListToolsAsync();
        Console.WriteLine("Tools discovered on the server:");
        foreach (var tool in mcpTools)
            Console.WriteLine($"  - {tool.Name}: {tool.Description}");
        Console.WriteLine();

        // 3) Build an Azure OpenAI-backed agent and hand it the MCP tools.
        AzureOpenAIClient openAIClient = string.IsNullOrEmpty(apiKey)
            ? new AzureOpenAIClient(new Uri(endpoint), new DefaultAzureCredential())
            : new AzureOpenAIClient(new Uri(endpoint), new ApiKeyCredential(apiKey));

        AIAgent agent = openAIClient
            .GetChatClient(deploymentName)
            .AsIChatClient()
            .AsAIAgent(new ChatClientAgentOptions
            {
                Name = "AcaMcpAgent",
                ChatOptions = new ChatOptions
                {
                    Instructions =
                        "You are a helpful assistant. When the user asks about weather or stock prices, " +
                        "use the provided tools. Be concise.",
                    Tools = mcpTools.Cast<AITool>().ToList(),
                }
            });

        // 4) A couple of demo prompts that should trigger tool calls.
        string[] prompts =
        {
            "What's the weather in Hyderabad?",
            "How much is MSFT trading at right now?",
            "Compare the weather in Seattle and London in one sentence."
        };

        foreach (var prompt in prompts)
        {
            Console.WriteLine($"You:   {prompt}");
            var response = await agent.RunAsync(prompt);
            Console.WriteLine($"Agent: {response.Text}\n");
        }
    }
}
