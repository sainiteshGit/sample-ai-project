using System.ClientModel;
using Azure.AI.OpenAI;
using Azure.Identity;
using Microsoft.Agents.AI;
using Microsoft.Extensions.Configuration;
using OpenAI.Responses;

namespace BackgroundResponsesSample;

/// <summary>
/// Two scenarios:
/// 1. Non-Streaming - Poll with continuation tokens until complete
/// 2. Streaming - Resume an interrupted stream using continuation tokens
/// </summary>
class Program
{
    static async Task Main(string[] args)
    {

        // Load configuration
        var configuration = new ConfigurationBuilder()
            .SetBasePath(Directory.GetCurrentDirectory())
            .AddJsonFile("appsettings.json", optional: true)
            .AddJsonFile("appsettings.Development.json", optional: true)
            .Build();

        var azureEndpoint = configuration["AzureOpenAI:Endpoint"];
        var azureApiKey = configuration["AzureOpenAI:ApiKey"];
        var deploymentName = configuration["AzureOpenAI:DeploymentName"] ?? "gpt-4o-mini";

        if (string.IsNullOrEmpty(azureEndpoint))
        {
            Console.WriteLine("Error: Set AzureOpenAI:Endpoint in appsettings.Development.json");
            return;
        }

        // Create Azure OpenAI client (API key or DefaultAzureCredential)
        AzureOpenAIClient openAIClient = string.IsNullOrEmpty(azureApiKey)
            ? new AzureOpenAIClient(new Uri(azureEndpoint), new DefaultAzureCredential())
            : new AzureOpenAIClient(new Uri(azureEndpoint), new ApiKeyCredential(azureApiKey));

        // Background responses require OpenAI Responses API (not ChatClient)
        AIAgent agent = openAIClient
            .GetResponsesClient(deploymentName)
            .AsAIAgent(
                instructions: "You are a helpful assistant. Answer concisely.",
                name: "BackgroundAgent");

        Console.WriteLine($"Using: {deploymentName} | Auth: {(string.IsNullOrEmpty(azureApiKey) ? "DefaultAzureCredential" : "API Key")}\n");

        // ── Demo 1: Non-Streaming with Polling ──
        await DemoPolling(agent);

        // ── Demo 2: Streaming with Resumption ──
        await DemoStreamResume(agent);

        Console.WriteLine("Done!");
    }

    /// <summary>
    /// Non-streaming: Send a request, poll with continuation token until complete.
    /// </summary>
    static async Task DemoPolling(AIAgent agent)
    {
        Console.WriteLine("━━━ Demo 1: Non-Streaming (Polling) ━━━\n");

        AgentRunOptions options = new() { AllowBackgroundResponses = true };
        AgentSession session = await agent.CreateSessionAsync();

        var prompt = "Explain the theory of general relativity in 3 paragraphs.";
        Console.WriteLine($"Prompt: \"{prompt}\"\n");

        // Send request
        AgentResponse response = await agent.RunAsync(prompt, session, options);

        int pollCount = 0;

        // Poll until ContinuationToken becomes null (= done)
        while (response.ContinuationToken is not null)
        {
            pollCount++;
            Console.WriteLine($"  Poll #{pollCount} — still processing...");
            await Task.Delay(TimeSpan.FromSeconds(2));

            options.ContinuationToken = response.ContinuationToken;
            response = await agent.RunAsync(session, options);
        }

        Console.WriteLine(pollCount > 0
            ? $"\n  Completed after {pollCount} poll(s).\n"
            : "  Completed immediately.\n");

        Console.WriteLine(response.Text);
        Console.WriteLine();
    }

    /// <summary>
    /// Streaming: Start a stream, simulate interruption, resume from where it stopped.
    /// </summary>
    static async Task DemoStreamResume(AIAgent agent)
    {
        Console.WriteLine("━━━ Demo 2: Streaming (Interrupt + Resume) ━━━\n");

        AgentRunOptions options = new() { AllowBackgroundResponses = true };
        AgentSession session = await agent.CreateSessionAsync();

        var prompt = "Write a 4-paragraph essay on why the ocean is important.";
        Console.WriteLine($"Prompt: \"{prompt}\"\n");

        AgentResponseUpdate? lastUpdate = null;
        int chunkCount = 0;

        // Stream — but break after 10 chunks to simulate interruption
        Console.ForegroundColor = ConsoleColor.Green;
        Console.WriteLine("[STREAMING]");
        Console.ResetColor();

        await foreach (var update in agent.RunStreamingAsync(prompt, session, options))
        {
            Console.Write(update.Text);
            lastUpdate = update;
            chunkCount++;

            if (chunkCount >= 10)
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.Write("\n\n  INTERRUPTED after 10 chunks!\n");
                Console.ResetColor();
                break;
            }
        }

        // Resume using the continuation token from the last chunk
        if (lastUpdate?.ContinuationToken is not null)
        {
            Console.WriteLine("  Resuming in 2 seconds...\n");
            await Task.Delay(TimeSpan.FromSeconds(2));

            options.ContinuationToken = lastUpdate.ContinuationToken;

            Console.ForegroundColor = ConsoleColor.Yellow;
            Console.WriteLine("[RESUMED]");
            Console.ResetColor();

            await foreach (var update in agent.RunStreamingAsync(session, options))
            {
                Console.Write(update.Text);
            }

            Console.WriteLine("\n");
        }
        else
        {
            Console.WriteLine("\n  Response completed before interruption point.\n");
        }
    }
}
