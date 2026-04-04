using System.ClientModel;
using Azure.AI.OpenAI;
using Azure.Identity;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using Microsoft.Extensions.Configuration;
using OpenAI.Responses;

namespace MultiModelDebate;

class Program
{
    static async Task Main(string[] args)
    {
        var configuration = new ConfigurationBuilder()
            .SetBasePath(Directory.GetCurrentDirectory())
            .AddJsonFile("appsettings.json", optional: true)
            .AddJsonFile("appsettings.Development.json", optional: true)
            .Build();

        var endpoint = configuration["AzureOpenAI:Endpoint"];
        var apiKey = configuration["AzureOpenAI:ApiKey"];
        var modelA = configuration["AzureOpenAI:ModelA"] ?? "gpt-4.1-mini";
        var modelB = configuration["AzureOpenAI:ModelB"] ?? "grok-4-1-fast-reasoning";
        var judgeModel = configuration["Debate:JudgeModel"] ?? modelB;
        var maxRounds = configuration.GetValue<int>("Debate:MaxRounds", 2);

        if (string.IsNullOrEmpty(endpoint))
        {
            Console.WriteLine("Error: Set AzureOpenAI:Endpoint in appsettings.Development.json");
            return;
        }

        AzureOpenAIClient openAIClient = string.IsNullOrEmpty(apiKey)
            ? new AzureOpenAIClient(new Uri(endpoint), new DefaultAzureCredential())
            : new AzureOpenAIClient(new Uri(endpoint), new ApiKeyCredential(apiKey));

        Console.WriteLine("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        Console.WriteLine("  Multi-Model Debate — Two Models, One Best Answer");
        Console.WriteLine("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        Console.WriteLine($"  Model A: {modelA}");
        Console.WriteLine($"  Model B: {modelB}");
        Console.WriteLine($"  Judge:   {judgeModel}");
        Console.WriteLine($"  Debate rounds: {maxRounds}");
        Console.WriteLine();

        // Helper: create agent using Responses API (GPT models) or Chat Completions (others)
        AIAgent CreateAgent(string deployment, string name, string instructions)
        {
            // GPT models support the Responses API; others fall back to Chat Completions
            bool useResponsesApi = deployment.StartsWith("gpt", StringComparison.OrdinalIgnoreCase);

            if (useResponsesApi)
            {
                return openAIClient
                    .GetResponsesClient(deployment)
                    .AsAIAgent(new ChatClientAgentOptions
                    {
                        Name = name,
                        ChatOptions = new() { Instructions = instructions },
                    });
            }
            else
            {
                IChatClient chatClient = openAIClient.GetChatClient(deployment).AsIChatClient();
                return chatClient.AsAIAgent(new ChatClientAgentOptions
                    {
                        Name = name,
                        ChatOptions = new() { Instructions = instructions },
                    });
            }
        }

        // Create agents with different reasoning styles (even if same model)
        AIAgent agentA = CreateAgent(modelA, "Pragmatist",
            "You are a pragmatic engineer. Prioritize practical tradeoffs, real-world constraints, and production experience. Be concise.");

        AIAgent agentB = CreateAgent(modelB, "Theorist",
            "You are a rigorous computer scientist. Prioritize correctness, formal guarantees, and theoretical foundations. Be concise.");

        AIAgent judgeAgent = CreateAgent(judgeModel, "Judge",
            "You are an impartial judge. Evaluate responses for accuracy, completeness, and practical usefulness. Synthesize the best answer.");

        var orchestrator = new DebateOrchestrator(
            agentA, $"{modelA} (Pragmatist)",
            agentB, $"{modelB} (Theorist)",
            judgeAgent, maxRounds);

        // ── Demo 1: Quick Consensus (no debate rounds) ──
        await Demo1_QuickConsensus(orchestrator);

        // ── Demo 2: Full Debate with Critique Rounds ──
        await Demo2_FullDebate(orchestrator);

        // ── Demo 3: Factual Dispute ──
        await Demo3_FactualDispute(orchestrator);

        // ── Demo 4: Interactive Mode ──
        await Demo4_Interactive(orchestrator);
    }

    static async Task Demo1_QuickConsensus(DebateOrchestrator orchestrator)
    {
        Console.WriteLine("━━━ Demo 1: Quick Consensus (no debate) ━━━\n");
        Console.WriteLine("  Question: What are the main benefits of microservices over monoliths?\n");

        var result = await orchestrator.RunConsensusAsync(
            "What are the main benefits of microservices over monoliths? Keep it to 3-4 points.");

        Console.WriteLine($"\n  📋 Final Answer:\n  {result.FinalAnswer}\n");
    }

    static async Task Demo2_FullDebate(DebateOrchestrator orchestrator)
    {
        Console.WriteLine("━━━ Demo 2: Full Debate with Critique Rounds ━━━\n");
        Console.WriteLine("  Question: Is Rust better than Go for building web backends?\n");

        var result = await orchestrator.RunDebateAsync(
            "Is Rust better than Go for building web backends? Give a definitive recommendation with reasoning.");

        Console.WriteLine($"\n  📋 Final Answer (after {result.Rounds.Count} debate rounds):");
        Console.WriteLine($"  {result.FinalAnswer}\n");
    }

    static async Task Demo3_FactualDispute(DebateOrchestrator orchestrator)
    {
        Console.WriteLine("━━━ Demo 3: Factual Dispute ━━━\n");
        Console.WriteLine("  Question: What is the time complexity of Dijkstra's algorithm?\n");

        var result = await orchestrator.RunDebateAsync(
            "What is the time complexity of Dijkstra's algorithm with a binary heap? Explain why.");

        Console.WriteLine($"\n  📋 Final Answer:");
        Console.WriteLine($"  {result.FinalAnswer}\n");
    }

    static async Task Demo4_Interactive(DebateOrchestrator orchestrator)
    {
        Console.WriteLine("━━━ Demo 4: Interactive Mode ━━━");
        Console.WriteLine("  Type a question for the models to debate. Type 'quit' to exit.\n");

        while (true)
        {
            Console.Write("  You: ");
            var input = Console.ReadLine();
            if (string.IsNullOrWhiteSpace(input) || input.Equals("quit", StringComparison.OrdinalIgnoreCase))
                break;

            Console.WriteLine();
            var result = await orchestrator.RunDebateAsync(input);
            Console.WriteLine($"\n  📋 Final Answer:\n  {result.FinalAnswer}\n");
        }
    }
}
