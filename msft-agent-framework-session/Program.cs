using System.ClientModel;
using System.Text.Json;
using Azure.AI.OpenAI;
using Azure.Identity;
using Microsoft.Agents.AI;
using Microsoft.Extensions.Configuration;
using OpenAI.Responses;

namespace AgentSessionSample;

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
        var deploymentName = configuration["AzureOpenAI:DeploymentName"] ?? "gpt-4o-mini";

        if (string.IsNullOrEmpty(endpoint))
        {
            Console.WriteLine("Error: Set AzureOpenAI:Endpoint in appsettings.Development.json");
            return;
        }

        AzureOpenAIClient openAIClient = string.IsNullOrEmpty(apiKey)
            ? new AzureOpenAIClient(new Uri(endpoint), new DefaultAzureCredential())
            : new AzureOpenAIClient(new Uri(endpoint), new ApiKeyCredential(apiKey));

        // Create agent using Responses API
        AIAgent agent = openAIClient
            .GetResponsesClient(deploymentName)
            .AsAIAgent(
                instructions: "You are a helpful assistant. Be concise and remember context from previous messages.",
                name: "SessionAgent");

        Console.WriteLine("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        Console.WriteLine("  Agent Sessions — Conversation State Management ");
        Console.WriteLine("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        Console.WriteLine($"  Model: {deploymentName}");
        Console.WriteLine();

        // ── Demo 1: Basic session — multi-turn memory ──
        await Demo1_BasicSession(agent);

        // ── Demo 2: Session isolation — separate conversations don't leak ──
        await Demo2_SessionIsolation(agent);

        // ── Demo 3: StateBag — storing custom state in a session ──
        await Demo3_StateBag(agent);

        // ── Demo 4: Serialization & Restoration — persist and resume sessions ──
        await Demo4_SerializationRestoration(agent);

        // ── Demo 5: Session with streaming — context preserved across streamed runs ──
        await Demo5_StreamingWithSession(agent);

        Console.WriteLine("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        Console.WriteLine("  All demos complete!");
        Console.WriteLine("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    }

    // ═══════════════════════════════════════════════════════
    // Demo 1: Basic Session — Multi-Turn Memory
    //
    // Shows: The simplest use of AgentSession. Create a session,
    // send multiple messages, and the agent remembers context
    // from previous turns. Without a session, each RunAsync
    // call would be stateless.
    // ═══════════════════════════════════════════════════════
    static async Task Demo1_BasicSession(AIAgent agent)
    {
        Console.WriteLine("━━━ Demo 1: Basic Session — Multi-Turn Memory ━━━\n");

        // Create a new session — this is the conversation state container
        AgentSession session = await agent.CreateSessionAsync();

        // Turn 1: Tell the agent something
        var prompt1 = "My name is Alice and I work at Contoso.";
        Console.WriteLine($"  You: {prompt1}");
        AgentResponse response1 = await agent.RunAsync(prompt1, session);
        Console.WriteLine($"  Agent: {response1.Text}\n");

        // Turn 2: Ask about what we just said — agent should remember
        var prompt2 = "What is my name and where do I work?";
        Console.WriteLine($"  You: {prompt2}");
        AgentResponse response2 = await agent.RunAsync(prompt2, session);
        Console.WriteLine($"  Agent: {response2.Text}\n");

        // Turn 3: Build on the context further
        var prompt3 = "I just got promoted to Senior Engineer.";
        Console.WriteLine($"  You: {prompt3}");
        AgentResponse response3 = await agent.RunAsync(prompt3, session);
        Console.WriteLine($"  Agent: {response3.Text}\n");

        // Turn 4: Ask the agent to summarize everything it knows
        var prompt4 = "Summarize everything you know about me in one sentence.";
        Console.WriteLine($"  You: {prompt4}");
        AgentResponse response4 = await agent.RunAsync(prompt4, session);
        Console.WriteLine($"  Agent: {response4.Text}\n");
    }

    // ═══════════════════════════════════════════════════════
    // Demo 2: Session Isolation — Separate Conversations
    //
    // Shows: Two sessions don't share context. What you tell
    // one agent session is invisible to the other. This is
    // critical for multi-user or multi-conversation scenarios.
    // ═══════════════════════════════════════════════════════
    static async Task Demo2_SessionIsolation(AIAgent agent)
    {
        Console.WriteLine("━━━ Demo 2: Session Isolation ━━━\n");

        // Create two independent sessions
        AgentSession sessionA = await agent.CreateSessionAsync();
        AgentSession sessionB = await agent.CreateSessionAsync();

        // Tell Session A a fact
        var promptA = "My favorite color is blue.";
        Console.WriteLine($"  [Session A] You: {promptA}");
        AgentResponse responseA = await agent.RunAsync(promptA, sessionA);
        Console.WriteLine($"  [Session A] Agent: {responseA.Text}\n");

        // Tell Session B a different fact
        var promptB = "My favorite color is red.";
        Console.WriteLine($"  [Session B] You: {promptB}");
        AgentResponse responseB = await agent.RunAsync(promptB, sessionB);
        Console.WriteLine($"  [Session B] Agent: {responseB.Text}\n");

        // Ask Session A — should say blue, not red
        var askA = "What is my favorite color?";
        Console.WriteLine($"  [Session A] You: {askA}");
        AgentResponse checkA = await agent.RunAsync(askA, sessionA);
        Console.WriteLine($"  [Session A] Agent: {checkA.Text}");

        // Ask Session B — should say red, not blue
        var askB = "What is my favorite color?";
        Console.WriteLine($"  [Session B] You: {askB}");
        AgentResponse checkB = await agent.RunAsync(askB, sessionB);
        Console.WriteLine($"  [Session B] Agent: {checkB.Text}\n");

        Console.WriteLine("  ✓ Sessions are isolated — each has its own conversation context.\n");
    }

    // ═══════════════════════════════════════════════════════
    // Demo 3: StateBag — Custom State Storage
    //
    // Shows: AgentSession has a StateBag property — an arbitrary
    // state container where you can store application-specific
    // data alongside the conversation. Think of it as a
    // dictionary that travels with the session.
    // ═══════════════════════════════════════════════════════
    static async Task Demo3_StateBag(AIAgent agent)
    {
        Console.WriteLine("━━━ Demo 3: StateBag — Custom State ━━━\n");

        AgentSession session = await agent.CreateSessionAsync();

        // Store custom state using SetValue<T>(key, value)
        // Note: StateBag requires reference types — use string for all values
        session.StateBag.SetValue("userId", "user-12345");
        session.StateBag.SetValue("tier", "premium");
        int turnCount = 0;
        session.StateBag.SetValue("turnCount", turnCount.ToString());

        Console.WriteLine("  Stored in StateBag:");
        Console.WriteLine($"    userId: {session.StateBag.GetValue<string>("userId")}");
        Console.WriteLine($"    tier: {session.StateBag.GetValue<string>("tier")}");
        Console.WriteLine($"    turnCount: {session.StateBag.GetValue<string>("turnCount")}\n");

        // Run a few turns, incrementing our custom counter
        string[] prompts = [
            "What's the capital of France?",
            "And what's its population?",
            "What language do they speak there?"
        ];

        foreach (var prompt in prompts)
        {
            // Increment our custom turn counter
            turnCount = int.Parse(session.StateBag.GetValue<string>("turnCount")!);
            session.StateBag.SetValue("turnCount", (turnCount + 1).ToString());

            Console.WriteLine($"  You (turn {session.StateBag.GetValue<string>("turnCount")}): {prompt}");
            AgentResponse response = await agent.RunAsync(prompt, session);
            Console.WriteLine($"  Agent: {response.Text}\n");
        }

        Console.WriteLine("  Final StateBag state:");
        Console.WriteLine($"    userId: {session.StateBag.GetValue<string>("userId")}");
        Console.WriteLine($"    tier: {session.StateBag.GetValue<string>("tier")}");
        Console.WriteLine($"    turnCount: {session.StateBag.GetValue<string>("turnCount")}\n");

        Console.WriteLine("  ✓ StateBag carries custom application state alongside conversation context.\n");
    }

    // ═══════════════════════════════════════════════════════
    // Demo 4: Serialization & Restoration
    //
    // Shows: Sessions can be serialized to a string and later
    // deserialized back. This is essential for:
    // - Persisting sessions across app restarts
    // - Storing sessions in a database or cache
    // - Transferring sessions between server instances
    // ═══════════════════════════════════════════════════════
    static async Task Demo4_SerializationRestoration(AIAgent agent)
    {
        Console.WriteLine("━━━ Demo 4: Serialization & Restoration ━━━\n");

        // Step 1: Create a session and have a conversation
        AgentSession session = await agent.CreateSessionAsync();
        session.StateBag.SetValue("createdAt", DateTime.UtcNow.ToString("o"));
        session.StateBag.SetValue("sessionLabel", "support-ticket-42");

        var prompt1 = "I'm having trouble with my Azure Function deployment. It times out after 30 seconds.";
        Console.WriteLine($"  You: {prompt1}");
        AgentResponse response1 = await agent.RunAsync(prompt1, session);
        Console.WriteLine($"  Agent: {response1.Text}\n");

        // Step 2: Serialize the session — returns a JsonElement
        JsonElement serialized = await agent.SerializeSessionAsync(session);
        string serializedJson = serialized.GetRawText();
        Console.WriteLine($"  Serialized session ({serializedJson.Length} chars)");
        Console.WriteLine($"  Preview: {Truncate(serializedJson, 120)}\n");

        // Simulate: store to database, transfer to another server, app restart, etc.
        // In production, you'd persist serializedJson to a database or cache.
        Console.WriteLine("  ... simulating app restart / transfer ...\n");

        // Step 3: Deserialize from the stored JsonElement and resume
        JsonElement toRestore = JsonDocument.Parse(serializedJson).RootElement;
        AgentSession restored = await agent.DeserializeSessionAsync(toRestore);

        Console.WriteLine("  Session restored. StateBag preserved:");
        Console.WriteLine($"    createdAt: {restored.StateBag.GetValue<string>("createdAt")}");
        Console.WriteLine($"    sessionLabel: {restored.StateBag.GetValue<string>("sessionLabel")}\n");

        // Step 4: Continue the conversation — agent should remember the deployment issue
        var prompt2 = "What was the issue I was telling you about?";
        Console.WriteLine($"  You: {prompt2}");
        AgentResponse response2 = await agent.RunAsync(prompt2, restored);
        Console.WriteLine($"  Agent: {response2.Text}\n");

        Console.WriteLine("  ✓ Session serialized, restored, and conversation context preserved.\n");
    }

    // ═══════════════════════════════════════════════════════
    // Demo 5: Streaming with Session
    //
    // Shows: Sessions work with streaming too. Each streamed
    // run within the same session preserves full context.
    // ═══════════════════════════════════════════════════════
    static async Task Demo5_StreamingWithSession(AIAgent agent)
    {
        Console.WriteLine("━━━ Demo 5: Streaming with Session ━━━\n");

        AgentSession session = await agent.CreateSessionAsync();

        // Turn 1: Non-streaming to establish context
        var setup = "I'm building a REST API for a bookstore. It needs endpoints for books, authors, and reviews.";
        Console.WriteLine($"  You: {setup}");
        AgentResponse setupResponse = await agent.RunAsync(setup, session);
        Console.WriteLine($"  Agent: {setupResponse.Text}\n");

        // Turn 2: Stream a follow-up that requires context from turn 1
        var followUp = "Now list just the HTTP endpoints you'd recommend. Be brief.";
        Console.WriteLine($"  You: {followUp}");
        Console.Write("  Agent: ");

        int chunkCount = 0;
        await foreach (var update in agent.RunStreamingAsync(followUp, session))
        {
            Console.Write(update.Text);
            chunkCount++;
        }

        Console.WriteLine($"\n\n  ({chunkCount} chunks streamed)");

        // Turn 3: Verify context is still intact after streaming
        var verify = "How many resource types did I mention earlier?";
        Console.WriteLine($"\n  You: {verify}");
        AgentResponse verifyResponse = await agent.RunAsync(verify, session);
        Console.WriteLine($"  Agent: {verifyResponse.Text}\n");

        Console.WriteLine("  ✓ Streaming runs preserve session context across turns.\n");
    }

    // ═══════════════════════════════════════════════════════
    static string Truncate(string text, int maxLength)
    {
        text = text.ReplaceLineEndings(" ");
        return text.Length <= maxLength ? text : text[..maxLength] + "...";
    }
}
