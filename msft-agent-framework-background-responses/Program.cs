using System.ClientModel;
using Azure.AI.OpenAI;
using Azure.Identity;
using Microsoft.Agents.AI;
using Microsoft.Extensions.Configuration;
using OpenAI.Responses;

namespace BackgroundResponses;

class Program
{
    const int MaxPolls = 20; // Safety cap to prevent infinite polling

    static async Task Main(string[] args)
    {
        var configuration = new ConfigurationBuilder()
            .SetBasePath(Directory.GetCurrentDirectory())
            .AddJsonFile("appsettings.json", optional: true)
            .AddJsonFile("appsettings.Development.json", optional: true)
            .Build();

        var endpoint = configuration["AzureOpenAI:Endpoint"];
        var apiKey = configuration["AzureOpenAI:ApiKey"];
        var deploymentName = configuration["AzureOpenAI:DeploymentName"] ?? "gpt-4o-mini";
        var initialPollDelay = configuration.GetValue<int>("BackgroundResponses:InitialPollDelayMs", 2000);
        var maxPollDelay = configuration.GetValue<int>("BackgroundResponses:MaxPollDelayMs", 30000);
        var backoffMultiplier = configuration.GetValue<double>("BackgroundResponses:BackoffMultiplier", 1.5);

        if (string.IsNullOrEmpty(endpoint))
        {
            Console.WriteLine("Error: Set AzureOpenAI:Endpoint in appsettings.Development.json");
            return;
        }

        AzureOpenAIClient openAIClient = string.IsNullOrEmpty(apiKey)
            ? new AzureOpenAIClient(new Uri(endpoint), new DefaultAzureCredential())
            : new AzureOpenAIClient(new Uri(endpoint), new ApiKeyCredential(apiKey));

        // Background responses require the Responses API (not ChatClient)
        AIAgent agent = openAIClient
            .GetResponsesClient(deploymentName)
            .AsAIAgent(
                instructions: "You are a helpful assistant. Be concise.",
                name: "BackgroundAgent");

        Console.WriteLine("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        Console.WriteLine("  Agent Background Responses — Continuation Tokens");
        Console.WriteLine("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        Console.WriteLine($"  Model: {deploymentName}");
        Console.WriteLine($"  Max polls: {MaxPolls}");
        Console.WriteLine();

        // ── Demo 1: Simplest — Enable background responses on a basic question ──
        await Demo1_SimpleBackgroundResponse(agent);

        // ── Demo 2: Non-Streaming Polling — watch the continuation token loop ──
        await Demo2_PollingWithToken(agent);

        // ── Demo 3: Streaming with Interruption & Resumption ──
        await Demo3_StreamingResume(agent);

        // ── Demo 4: Exponential Backoff — production-grade polling ──
        await Demo4_ExponentialBackoff(agent, initialPollDelay, maxPollDelay, backoffMultiplier);

        Console.WriteLine("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        Console.WriteLine("  All demos complete!");
        Console.WriteLine("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    }

    // ═══════════════════════════════════════════════════════
    // Demo 1: Simplest — just enable AllowBackgroundResponses
    //
    // Shows: The minimal code change. A short prompt will likely
    // complete immediately (ContinuationToken is null on first call).
    // ═══════════════════════════════════════════════════════
    static async Task Demo1_SimpleBackgroundResponse(AIAgent agent)
    {
        Console.WriteLine("━━━ Demo 1: Simplest Background Response ━━━\n");

        // The only change from a normal agent call: AllowBackgroundResponses = true
        AgentRunOptions options = new() { AllowBackgroundResponses = true };
        AgentSession session = await agent.CreateSessionAsync();

        var prompt = "What is 2 + 2?";
        Console.WriteLine($"  Prompt: \"{prompt}\"");

        var sw = System.Diagnostics.Stopwatch.StartNew();
        AgentResponse response = await agent.RunAsync(prompt, session, options);

        // For a simple question, ContinuationToken will likely be null → immediate
        bool wasBackground = response.ContinuationToken is not null;

        // If it did go background, poll (unlikely for this prompt)
        int pollCount = 0;
        while (response.ContinuationToken is not null && pollCount < MaxPolls)
        {
            pollCount++;
            await Task.Delay(TimeSpan.FromSeconds(2));
            options.ContinuationToken = response.ContinuationToken;
            response = await agent.RunAsync(session, options);
        }
        sw.Stop();

        Console.WriteLine($"  ContinuationToken returned: {wasBackground}");
        Console.WriteLine($"  Mode: {(wasBackground ? $"BACKGROUND ({pollCount} polls)" : "IMMEDIATE")}");
        Console.WriteLine($"  Time: {sw.Elapsed.TotalSeconds:F1}s");
        Console.WriteLine($"  Answer: {response.Text}");
        Console.WriteLine();
    }

    // ═══════════════════════════════════════════════════════
    // Demo 2: Non-Streaming Polling with continuation token
    //
    // Shows: The full polling loop. A moderate prompt that may
    // trigger background processing. We poll every 2s with a
    // max poll cap for safety.
    // ═══════════════════════════════════════════════════════
    static async Task Demo2_PollingWithToken(AIAgent agent)
    {
        Console.WriteLine("━━━ Demo 2: Non-Streaming Polling ━━━\n");

        AgentRunOptions options = new() { AllowBackgroundResponses = true };
        AgentSession session = await agent.CreateSessionAsync();

        var prompt = "List 5 benefits of cloud computing in one sentence each.";
        Console.WriteLine($"  Prompt: \"{prompt}\"\n");

        var sw = System.Diagnostics.Stopwatch.StartNew();

        // Initial request
        AgentResponse response = await agent.RunAsync(prompt, session, options);
        int pollCount = 0;

        // Poll until ContinuationToken is null (= complete) or max polls reached
        while (response.ContinuationToken is not null && pollCount < MaxPolls)
        {
            pollCount++;
            Console.WriteLine($" Poll #{pollCount} — still processing... ({sw.Elapsed.TotalSeconds:F1}s)");
            await Task.Delay(TimeSpan.FromSeconds(2));

            options.ContinuationToken = response.ContinuationToken;
            response = await agent.RunAsync(session, options);
        }

        sw.Stop();

        if (pollCount >= MaxPolls && response.ContinuationToken is not null)
        {
            Console.WriteLine($"\n  Hit max poll limit ({MaxPolls}). Response may be partial.\n");
        }
        else if (pollCount > 0)
        {
            Console.WriteLine($"\n  Completed after {pollCount} poll(s) in {sw.Elapsed.TotalSeconds:F1}s\n");
        }
        else
        {
            Console.WriteLine($" Completed immediately in {sw.Elapsed.TotalSeconds:F1}s\n");
        }

        Console.WriteLine($"  Response ({response.Text?.Length ?? 0} chars):");
        Console.WriteLine($"  {Truncate(response.Text ?? "(empty)", 250)}");
        Console.WriteLine();
    }

    // ═══════════════════════════════════════════════════════
    // Demo 3: Streaming with Interruption & Resumption
    //
    // Shows: Streaming chunks in real-time, simulating a network
    // interruption after N chunks, then resuming from exactly
    // where it left off using the continuation token.
    // ═══════════════════════════════════════════════════════
    static async Task Demo3_StreamingResume(AIAgent agent)
    {
        Console.WriteLine("━━━ Demo 3: Streaming (Interrupt + Resume) ━━━\n");

        AgentRunOptions options = new() { AllowBackgroundResponses = true };
        AgentSession session = await agent.CreateSessionAsync();

        var prompt = "Explain why sleep is important for health in 2 paragraphs.";
        Console.WriteLine($"  Prompt: \"{prompt}\"\n");

        AgentResponseUpdate? lastUpdate = null;
        int chunkCount = 0;

        // Stream — break after 10 chunks to simulate interruption
        Console.ForegroundColor = ConsoleColor.Green;
        Console.WriteLine("  [STREAMING]");
        Console.ResetColor();
        Console.Write("  ");

        await foreach (var update in agent.RunStreamingAsync(prompt, session, options))
        {
            Console.Write(update.Text);
            lastUpdate = update;
            chunkCount++;

            if (chunkCount >= 10)
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.Write($"\n\n  ⚡ INTERRUPTED after {chunkCount} chunks!\n");
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
            Console.WriteLine("  [RESUMED]");
            Console.ResetColor();
            Console.Write("  ");

            int resumeChunks = 0;
            await foreach (var update in agent.RunStreamingAsync(session, options))
            {
                Console.Write(update.Text);
                resumeChunks++;
            }

            Console.WriteLine($"\n\n  Resumed and received {resumeChunks} additional chunks.\n");
        }
        else
        {
            Console.WriteLine("\n Response completed before interruption point.\n");
        }
    }

    // ═══════════════════════════════════════════════════════
    // Demo 4: Exponential Backoff — production-grade polling
    //
    // Shows: Instead of fixed 2s intervals, use exponential backoff
    // (2s → 3s → 4.5s → ...) with a configurable max. This is the
    // best practice for production to avoid overwhelming the service.
    // ═══════════════════════════════════════════════════════
    static async Task Demo4_ExponentialBackoff(AIAgent agent, int initialDelayMs, int maxDelayMs, double multiplier)
    {
        Console.WriteLine("━━━ Demo 4: Exponential Backoff Polling ━━━\n");

        AgentRunOptions options = new() { AllowBackgroundResponses = true };
        AgentSession session = await agent.CreateSessionAsync();

        var prompt = "What are the 3 main differences between REST and GraphQL?";
        Console.WriteLine($"  Prompt: \"{prompt}\"");
        Console.WriteLine($"  Backoff: start={initialDelayMs}ms, multiplier={multiplier}x, max={maxDelayMs}ms\n");

        var sw = System.Diagnostics.Stopwatch.StartNew();
        AgentResponse response = await agent.RunAsync(prompt, session, options);

        int pollCount = 0;
        double currentDelay = initialDelayMs;

        while (response.ContinuationToken is not null && pollCount < MaxPolls)
        {
            pollCount++;
            Console.WriteLine($"  ⏳ Poll #{pollCount} — waiting {currentDelay:F0}ms... ({sw.Elapsed.TotalSeconds:F1}s elapsed)");

            await Task.Delay(TimeSpan.FromMilliseconds(currentDelay));

            options.ContinuationToken = response.ContinuationToken;
            response = await agent.RunAsync(session, options);

            // Exponential backoff with cap
            currentDelay = Math.Min(currentDelay * multiplier, maxDelayMs);
        }

        sw.Stop();

        if (pollCount >= MaxPolls && response.ContinuationToken is not null)
            Console.WriteLine($"\n  Hit max poll limit ({MaxPolls}). Response may be partial.");
        else if (pollCount > 0)
            Console.WriteLine($"\n  Completed after {pollCount} poll(s) in {sw.Elapsed.TotalSeconds:F1}s");
        else
            Console.WriteLine($"  Completed immediately in {sw.Elapsed.TotalSeconds:F1}s");

        Console.WriteLine($"  Response ({response.Text?.Length ?? 0} chars): {Truncate(response.Text ?? "(empty)", 250)}");
        Console.WriteLine();
    }

    // ═══════════════════════════════════════════════════════
    static string Truncate(string text, int maxLength)
    {
        text = text.ReplaceLineEndings(" ");
        return text.Length <= maxLength ? text : text[..maxLength] + "...";
    }
}
