using System.ClientModel;
using System.Text.Json;
using Azure.AI.OpenAI;
using Azure.Identity;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using Microsoft.Extensions.Configuration;
using OpenAI.Chat;

namespace ChatHistoryProviderSample;

/// <summary>
/// Sample: Customer Support Chat Agent with Persistent History
/// 
/// Use Case: A customer support bot that remembers previous conversations.
/// - User returns next day and says "What was my order number again?"
/// - Agent retrieves context from Cosmos DB and provides accurate response
/// 
/// Why This Matters:
/// - Default in-memory history is lost when the app restarts
/// - Production apps need persistent, distributed storage
/// - Multi-instance deployments require shared state
/// 
/// This sample uses the official Microsoft.Agents.AI.CosmosNoSql package
/// which provides CosmosChatHistoryProvider out of the box.
/// </summary>
class Program
{
    static async Task Main(string[] args)
    {
        Console.WriteLine("===========================================");
        Console.WriteLine("  Customer Support Agent with Chat History ");
        Console.WriteLine("  (Using Microsoft.Agents.AI.CosmosNoSql)  ");
        Console.WriteLine("===========================================\n");

        // Load configuration
        var configuration = new ConfigurationBuilder()
            .SetBasePath(Directory.GetCurrentDirectory())
            .AddJsonFile("appsettings.json", optional: true)
            .AddJsonFile("appsettings.Development.json", optional: true)
            .AddUserSecrets<Program>(optional: true)
            .Build();

        var azureEndpoint = configuration["AzureOpenAI:Endpoint"];
        var azureApiKey = configuration["AzureOpenAI:ApiKey"];
        var deploymentName = configuration["AzureOpenAI:DeploymentName"] ?? "gpt-4o-mini";
        var cosmosConnectionString = configuration["CosmosDb:ConnectionString"];
        var cosmosEndpoint = configuration["CosmosDb:Endpoint"];
        var databaseName = configuration["CosmosDb:DatabaseName"] ?? "AgentChatHistory";
        var containerName = configuration["CosmosDb:ContainerName"] ?? "ChatMessages";

        // Validate configuration
        if (string.IsNullOrEmpty(azureEndpoint))
        {
            Console.WriteLine("Error: Azure OpenAI endpoint not configured.");
            Console.WriteLine("   Set AzureOpenAI:Endpoint in appsettings.Development.json");
            return;
        }

        if (string.IsNullOrEmpty(azureApiKey))
        {
            Console.WriteLine("Error: Azure OpenAI API key not configured.");
            Console.WriteLine("   Set AzureOpenAI:ApiKey in appsettings.Development.json");
            return;
        }

        // Determine storage mode
        bool useCosmosDb = !string.IsNullOrEmpty(cosmosConnectionString) || !string.IsNullOrEmpty(cosmosEndpoint);

        if (useCosmosDb)
        {
            Console.WriteLine("Using Cosmos DB for chat history storage");
            Console.WriteLine($"   Database: {databaseName}, Container: {containerName}\n");
        }
        else
        {
            Console.WriteLine("No Cosmos DB configured - using in-memory storage");
            Console.WriteLine("   (History will be lost when app restarts)\n");
        }

        // Create the Azure OpenAI client with API key authentication
        Console.WriteLine("Initializing Customer Support Agent...");
        var openAIClient = new AzureOpenAIClient(
            new Uri(azureEndpoint),
            new ApiKeyCredential(azureApiKey));

        // Get the IChatClient from Azure OpenAI
        IChatClient chatClient = openAIClient.GetChatClient(deploymentName).AsIChatClient();

        // Create agent options with instructions
        var agentOptions = new ChatClientAgentOptions
        {
            Name = "CustomerSupportAgent",
            Description = "A helpful customer support agent for TechGadgets Inc.",
            ChatOptions = new ChatOptions
            {
                Instructions = """
                    You are a helpful customer support agent for TechGadgets Inc.
                    
                    Your responsibilities:
                    - Help customers with order inquiries
                    - Provide product information
                    - Handle returns and exchanges
                    - Remember context from the conversation
                    
                    Always be polite and professional. If you helped the customer 
                    earlier in the conversation, reference that context.
                    """
            }
        };

        // Configure the ChatHistoryProvider based on the configuration
        if (useCosmosDb)
        {
            // Set up the ChatHistoryProviderFactory to create CosmosChatHistoryProvider instances
            if (!string.IsNullOrEmpty(cosmosConnectionString))
            {
                // Connection string authentication
                agentOptions.ChatHistoryProviderFactory = (context, ct) => 
                    new ValueTask<ChatHistoryProvider>(
                        new CosmosChatHistoryProvider(cosmosConnectionString, databaseName, containerName));
            }
            else if (!string.IsNullOrEmpty(cosmosEndpoint))
            {
                // Managed Identity / DefaultAzureCredential authentication
                agentOptions.ChatHistoryProviderFactory = (context, ct) => 
                    new ValueTask<ChatHistoryProvider>(
                        new CosmosChatHistoryProvider(cosmosEndpoint, new DefaultAzureCredential(), databaseName, containerName));
            }
        }

        // Create the agent using the ChatClientAgent constructor
        var agent = new ChatClientAgent(chatClient, agentOptions);

        Console.WriteLine("Agent ready!\n");

        // Start a new session
        var session = await agent.GetNewSessionAsync();
        Console.WriteLine($"---Session started: {(useCosmosDb ? "Persisted to Cosmos DB" : "In-memory only")}\n");

        // Interactive chat loop
        Console.WriteLine("Type your message (or 'quit' to exit, 'save' to serialize session):\n");

        while (true)
        {
            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.Write("You: ");
            Console.ResetColor();

            var userInput = Console.ReadLine();

            if (string.IsNullOrWhiteSpace(userInput))
                continue;

            if (userInput.Equals("quit", StringComparison.OrdinalIgnoreCase))
            {
                Console.WriteLine("\n  for using Customer Support.");
                break;
            }

            if (userInput.Equals("save", StringComparison.OrdinalIgnoreCase))
            {
                // Demonstrate session serialization
                var serializedSession = session.Serialize();
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine($"\n Session serialized:");
                Console.WriteLine(JsonSerializer.Serialize(serializedSession, new JsonSerializerOptions { WriteIndented = true }));
                Console.WriteLine("   (This can be stored and used to resume the conversation later)\n");
                Console.ResetColor();
                continue;
            }

            try
            {
                // Get response from agent - the session manages chat history automatically
                Console.ForegroundColor = ConsoleColor.Green;
                Console.Write("\nAgent: ");
                Console.ResetColor();

                // RunAsync adds the user message to the session and returns the agent response
                var response = await agent.RunAsync(userInput, session);
                
                // Print the response text
                foreach (var message in response.Messages)
                {
                    Console.WriteLine(message.Text);
                }
                Console.WriteLine();
            }
            catch (Exception ex)
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine($"\nError: {ex.Message}\n");
                Console.ResetColor();
            }
        }
    }
}
