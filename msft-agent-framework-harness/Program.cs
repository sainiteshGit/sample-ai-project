using System.ClientModel;
using System.ComponentModel;
using System.Text.Json;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using Microsoft.Extensions.Configuration;
using OpenAI;
using OpenAI.Responses;

const string prompt = "Find a laptop under $1000, choose the one with the most RAM, and add it to my wishlist.";

if (args.Length > 1 || (args.Length == 1 && args[0] is not ("--live" or "--help")))
{
    Console.Error.WriteLine("Usage: dotnet run [--live|--help]");
    return 1;
}

if (args is ["--help"])
{
    Console.WriteLine("Run dotnet run (or dotnet run -- --live) to call the configured Azure AI Foundry model.");
    return 0;
}

IConfiguration config = new ConfigurationBuilder()
    .SetBasePath(AppContext.BaseDirectory)
    .AddJsonFile("appsettings.json")
    .AddJsonFile("appsettings.Development.json", optional: true)
    .Build();
string? endpoint = Environment.GetEnvironmentVariable("AZURE_OPENAI_ENDPOINT") ?? config["AzureOpenAI:Endpoint"];
string? deployment = Environment.GetEnvironmentVariable("AZURE_OPENAI_DEPLOYMENT") ?? config["AzureOpenAI:DeploymentName"];
string? apiKey = Environment.GetEnvironmentVariable("AZURE_OPENAI_API_KEY") ?? config["AzureOpenAI:ApiKey"];
if (!Uri.TryCreate(endpoint, UriKind.Absolute, out Uri? endpointUri) ||
    endpointUri.Scheme != Uri.UriSchemeHttps)
{
    Console.Error.WriteLine("Set an HTTPS AzureOpenAI:Endpoint in appsettings.Development.json or AZURE_OPENAI_ENDPOINT.");
    return 1;
}

if (string.IsNullOrWhiteSpace(deployment))
{
    Console.Error.WriteLine("Set AzureOpenAI:DeploymentName in appsettings.Development.json or AZURE_OPENAI_DEPLOYMENT.");
    return 1;
}

if (string.IsNullOrWhiteSpace(apiKey))
{
    apiKey = ReadApiKey();
    if (string.IsNullOrWhiteSpace(apiKey))
    {
        Console.Error.WriteLine("No API key was entered. Set AzureOpenAI:ApiKey in local settings, set AZURE_OPENAI_API_KEY, or run from an interactive terminal.");
        return 1;
    }
}

var openAIClient = new OpenAIClient(new ApiKeyCredential(apiKey), new OpenAIClientOptions
{
    Endpoint = endpointUri
});
ResponsesClient responsesClient = openAIClient.GetResponsesClient();
IChatClient chatClient = new ModelCallLoggingChatClient(responsesClient.AsIChatClient(deployment), "Azure AI Foundry Responses API");
Console.WriteLine($"Model: Azure AI Foundry deployment '{deployment}' (live)");

using var clientLifetime = chatClient;
var shop = new Shop();
AIAgent agent = chatClient.AsHarnessAgent(new HarnessAgentOptions
{
    Name = "ShoppingAssistant",
    ChatOptions = new ChatOptions
    {
        Instructions = "You are a shopping assistant. Search for a laptop under $1000, " +
            "choose the one with the most RAM from the results, and request adding it to the wishlist. " +
            "Report accurately whether the tool succeeded or was denied.",
        Tools =
        [
            AIFunctionFactory.Create(shop.SearchProducts),
            new ApprovalRequiredAIFunction(AIFunctionFactory.Create(shop.AddToWishlist))
        ]
    },
    // Keep this example focused on the model/tool loop and explicit approval.
    DisableTodoProvider = true,
    DisableAgentModeProvider = true,
    DisableFileMemory = true,
    DisableAgentSkillsProvider = true,
    DisableWebSearch = true,
    DisableToolAutoApproval = true
});

AgentSession session = await agent.CreateSessionAsync();
Console.WriteLine($"User: {prompt}");
AgentResponse response = await agent.RunAsync(prompt, session);

while (true)
{
    var requests = response.Messages
        .SelectMany(message => message.Contents)
        .OfType<ToolApprovalRequestContent>()
        .ToList();
    if (requests.Count == 0)
    {
        break;
    }

    var decisions = new List<AIContent>();
    foreach (ToolApprovalRequestContent request in requests)
    {
        if (request.ToolCall is not FunctionCallContent call)
        {
            throw new InvalidOperationException("The approval request did not contain a function call.");
        }

        Console.WriteLine($"Approval requested: {call.Name} {JsonSerializer.Serialize(call.Arguments)}");
        Console.Write("Approve? [y/N]: ");
        string? answer = Console.ReadLine();
        if (answer is null)
        {
            Console.Error.WriteLine("Input closed; stopping without submitting pending approval decisions.");
            Console.WriteLine($"Wishlist: {(shop.Wishlist.Count == 0 ? "(empty)" : string.Join(", ", shop.Wishlist))}");
            return 1;
        }

        bool approved = string.Equals(answer.Trim(), "y", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(answer.Trim(), "yes", StringComparison.OrdinalIgnoreCase);
        Console.WriteLine(approved ? "Decision: approved" : "Decision: denied");
        decisions.Add(request.CreateResponse(approved));
    }

    response = await agent.RunAsync(new ChatMessage(ChatRole.User, decisions), session);
}

Console.WriteLine($"Agent: {response.Text}");
Console.WriteLine($"Wishlist: {(shop.Wishlist.Count == 0 ? "(empty)" : string.Join(", ", shop.Wishlist))}");
return 0;

static string? ReadApiKey()
{
    if (Console.IsInputRedirected)
    {
        return null;
    }

    Console.Write("Azure OpenAI API key (input hidden): ");
    var key = new System.Text.StringBuilder();
    while (true)
    {
        ConsoleKeyInfo input = Console.ReadKey(intercept: true);
        if (input.Key == ConsoleKey.Enter)
        {
            Console.WriteLine();
            return key.ToString();
        }

        if (input.Key == ConsoleKey.Backspace)
        {
            if (key.Length > 0)
            {
                key.Length--;
            }

            continue;
        }

        if (!char.IsControl(input.KeyChar))
        {
            key.Append(input.KeyChar);
        }
    }
}

internal sealed class Shop
{
    private static readonly Product[] Products =
    [
        new(42, "Northstar 14 laptop", 899, 16),
        new(43, "Valley 15 laptop", 1099, 32),
        new(44, "Cedar 13 laptop", 749, 8),
        new(45, "Harbor 14 laptop", 1000, 32)
    ];

    public List<string> Wishlist { get; } = [];

    [Description("Search the demo product catalog for products strictly below the supplied price in US dollars.")]
    public string SearchProducts(
        [Description("Product type, for example laptop.")] string query,
        [Description("Exclusive price limit in US dollars.")] decimal maxPrice)
    {
        Console.WriteLine($"Tool executed: SearchProducts(query={query}, maxPrice={maxPrice})");
        string result = JsonSerializer.Serialize(Products.Where(product =>
            product.Name.Contains(query, StringComparison.OrdinalIgnoreCase) && product.Price < maxPrice));
        Console.WriteLine($"Tool result: {result}");
        return result;
    }

    [Description("Add a catalog product to the in-memory wishlist using its product ID.")]
    public string AddToWishlist([Description("ID of a product returned by SearchProducts.")] int productId)
    {
        Product product = Products.FirstOrDefault(item => item.Id == productId)
            ?? throw new ArgumentException($"Unknown product ID: {productId}", nameof(productId));
        Console.WriteLine($"Tool executed: AddToWishlist(productId={productId})");
        Wishlist.Add(product.Name);
        return $"Added {product.Name} to the wishlist.";
    }

    private sealed record Product(int Id, string Name, decimal Price, int MemoryGb);
}
