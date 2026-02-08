using System.ClientModel;
using System.Text.Json;
using Azure.AI.OpenAI;
using Azure.Identity;
using Azure.Monitor.OpenTelemetry.Exporter;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;
using OpenAI.Chat;
using OpenTelemetry;
using OpenTelemetry.Logs;
using OpenTelemetry.Metrics;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;

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
/// 
/// Observability:
/// - OpenTelemetry integration for traces, metrics, and logs
/// - Supports Azure Monitor (Application Insights) and Aspire Dashboard
/// - GenAI Semantic Conventions for LLM observability
/// </summary>
class Program
{
    private const string ServiceName = "ChatHistoryProviderSample";
    private const string SourceName = "ChatHistoryProviderSample";

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
        
        // Observability configuration
        var appInsightsConnectionString = configuration["ApplicationInsights:ConnectionString"];
        var otlpEndpoint = configuration["OpenTelemetry:OtlpEndpoint"] ?? "http://localhost:4317";
        var enableSensitiveData = configuration.GetValue<bool>("OpenTelemetry:EnableSensitiveData", false);

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

        // OpenTelemetry Setup for Observability
        var resourceBuilder = ResourceBuilder
            .CreateDefault()
            .AddService(ServiceName);

        // Configure Tracer Provider
        var tracerProviderBuilder = Sdk.CreateTracerProviderBuilder()
            .SetResourceBuilder(resourceBuilder)
            .AddSource(SourceName)
            .AddSource("*Microsoft.Extensions.AI")     // Chat client telemetry
            .AddSource("*Microsoft.Extensions.Agents*") // Agent telemetry
            .AddConsoleExporter();                      // Console output for debugging

        // Add Azure Monitor exporter if Application Insights is configured
        if (!string.IsNullOrEmpty(appInsightsConnectionString))
        {
            tracerProviderBuilder.AddAzureMonitorTraceExporter(options => 
                options.ConnectionString = appInsightsConnectionString);
            Console.WriteLine("✓ Azure Monitor (Application Insights) tracing enabled");
        }
        else
        {
            // Use OTLP exporter for Aspire Dashboard or other backends
            tracerProviderBuilder.AddOtlpExporter(options => 
            {
                options.Endpoint = new Uri(otlpEndpoint);
                options.Protocol = OpenTelemetry.Exporter.OtlpExportProtocol.HttpProtobuf;
            });
            Console.WriteLine($"✓ OTLP tracing enabled (endpoint: {otlpEndpoint})");
        }

        var tracerProvider = tracerProviderBuilder.Build();

        // Configure Meter Provider for metrics
        var meterProviderBuilder = Sdk.CreateMeterProviderBuilder()
            .SetResourceBuilder(resourceBuilder)
            .AddMeter("*Microsoft.Agents.AI")           // Agent Framework metrics
            .AddConsoleExporter();

        if (!string.IsNullOrEmpty(appInsightsConnectionString))
        {
            meterProviderBuilder.AddAzureMonitorMetricExporter(options => 
                options.ConnectionString = appInsightsConnectionString);
            Console.WriteLine("✓ Azure Monitor metrics enabled");
        }
        else
        {
            meterProviderBuilder.AddOtlpExporter(options => 
            {
                options.Endpoint = new Uri(otlpEndpoint);
                options.Protocol = OpenTelemetry.Exporter.OtlpExportProtocol.HttpProtobuf;
            });
            Console.WriteLine($"✓ OTLP metrics enabled");
        }

        var meterProvider = meterProviderBuilder.Build();

        // Configure Logger Factory with OpenTelemetry
        using var loggerFactory = LoggerFactory.Create(builder =>
        {
            builder.AddConsole();
            builder.AddOpenTelemetry(options =>
            {
                options.SetResourceBuilder(resourceBuilder);
                options.IncludeFormattedMessage = true;
                options.IncludeScopes = true;
                
                if (!string.IsNullOrEmpty(appInsightsConnectionString))
                {
                    options.AddAzureMonitorLogExporter(exporterOptions => 
                        exporterOptions.ConnectionString = appInsightsConnectionString);
                }
                else
                {
                    options.AddOtlpExporter(exporterOptions => 
                    {
                        exporterOptions.Endpoint = new Uri(otlpEndpoint);
                        exporterOptions.Protocol = OpenTelemetry.Exporter.OtlpExportProtocol.HttpProtobuf;
                    });
                }
            });
            builder.SetMinimumLevel(LogLevel.Information);
        });

        var logger = loggerFactory.CreateLogger<Program>();
        logger.LogInformation("OpenTelemetry observability configured for {ServiceName}", ServiceName);
        Console.WriteLine($"✓ Sensitive data logging: {(enableSensitiveData ? "ENABLED (development only!)" : "disabled")}\n");

        // Create the Azure OpenAI client with API key authentication
        Console.WriteLine("Initializing Customer Support Agent...");
        var openAIClient = new AzureOpenAIClient(
            new Uri(azureEndpoint),
            new ApiKeyCredential(azureApiKey));

        // Get the IChatClient from Azure OpenAI with OpenTelemetry instrumentation
        IChatClient chatClient = openAIClient
            .GetChatClient(deploymentName)
            .AsIChatClient()
            .AsBuilder()
            .UseOpenTelemetry(sourceName: SourceName, configure: cfg => cfg.EnableSensitiveData = enableSensitiveData)
            .Build();

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

        // Create the agent using the ChatClientAgent constructor with OpenTelemetry
        var agent = new ChatClientAgent(chatClient, agentOptions)
            .AsBuilder()
            .UseOpenTelemetry(sourceName: SourceName, configure: cfg => cfg.EnableSensitiveData = enableSensitiveData)
            .Build();

        logger.LogInformation("Agent {AgentName} initialized with OpenTelemetry instrumentation", agentOptions.Name);
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
                logger.LogInformation("User input received: {InputLength} characters", userInput.Length);
                
                // Get response from agent - the session manages chat history automatically
                Console.ForegroundColor = ConsoleColor.Green;
                Console.Write("\nAgent: ");
                Console.ResetColor();

                // RunAsync adds the user message to the session and returns the agent response
                var response = await agent.RunAsync(userInput, session);
                
                logger.LogInformation("Agent responded with {MessageCount} message(s)", response.Messages.Count);
                
                // Print the response text
                foreach (var message in response.Messages)
                {
                    Console.WriteLine(message.Text);
                }
                Console.WriteLine();
            }
            catch (Exception ex)
            {
                logger.LogError(ex, "Error processing user request");
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine($"\nError: {ex.Message}\n");
                Console.ResetColor();
            }
        }

        // Cleanup OpenTelemetry providers
        logger.LogInformation("Shutting down observability providers...");
        tracerProvider?.Dispose();
        meterProvider?.Dispose();
    }
}
