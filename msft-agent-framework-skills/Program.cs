using System.ClientModel;
using Azure.AI.OpenAI;
using Azure.Identity;
using Microsoft.Agents.AI;
using Microsoft.Extensions.Configuration;
using OpenAI.Responses;

namespace AgentSkillsSample;

/// <summary>
/// Demonstrates the Microsoft Agent Framework Agent Skills pattern.
/// 
/// Agent Skills are portable packages of instructions, scripts, and resources
/// that give agents specialized capabilities via progressive disclosure:
///   1. Advertise — Skill names/descriptions injected into system prompt
///   2. Load — Agent calls load_skill to get full instructions
///   3. Read resources — Agent calls read_skill_resource for supplementary files
/// 
/// This sample includes three skills:
///   - expense-report: Validates expenses against company policy
///   - code-review: Reviews code for quality and security
///   - weather-lookup: Provides weather information for locations
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
            Console.WriteLine("Copy appsettings.Development.json.template to appsettings.Development.json and fill in your values.");
            return;
        }

        // Create Azure OpenAI client (API key or DefaultAzureCredential)
        AzureOpenAIClient openAIClient = string.IsNullOrEmpty(azureApiKey)
            ? new AzureOpenAIClient(new Uri(azureEndpoint), new DefaultAzureCredential())
            : new AzureOpenAIClient(new Uri(azureEndpoint), new ApiKeyCredential(azureApiKey));

        // ── Set up the Skills Provider ──
        // FileAgentSkillsProvider discovers SKILL.md files from the skills directory
        // and exposes load_skill, read_skill_resource tools to the agent.
        var skillsProvider = new FileAgentSkillsProvider(
            skillPath: Path.Combine(AppContext.BaseDirectory, "skills"));

        // Create an agent with the skills provider as a context provider
        AIAgent agent = openAIClient
            .GetResponsesClient(deploymentName)
            .AsAIAgent(new ChatClientAgentOptions
            {
                Name = "SkillsAgent",
                ChatOptions = new()
                {
                    Instructions = "You are a helpful assistant with access to specialized skills. Use them when a task matches a skill's domain.",
                },
                AIContextProviders = [skillsProvider],
            });

        Console.WriteLine("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        Console.WriteLine("  Microsoft Agent Framework — Skills Demo");
        Console.WriteLine("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        Console.WriteLine($"Model: {deploymentName}");
        Console.WriteLine($"Auth: {(string.IsNullOrEmpty(azureApiKey) ? "DefaultAzureCredential" : "API Key")}");
        Console.WriteLine($"Skills directory: {Path.Combine(AppContext.BaseDirectory, "skills")}");
        Console.WriteLine();

        // ── Demo 1: Expense Report Skill ──
        await RunDemo(agent, "Expense Report Skill",
            "Are tips reimbursable? I left a 25% tip on a $80 taxi ride.");

        // ── Demo 2: Code Review Skill ──
        await RunDemo(agent, "Code Review Skill",
            """
            Review this C# code for issues:
            
            public string GetUser(string id)
            {
                var query = "SELECT * FROM Users WHERE Id = '" + id + "'";
                var result = db.Execute(query);
                return result.ToString();
            }
            """);

        // ── Demo 3: Weather Lookup Skill ──
        await RunDemo(agent, "Weather Lookup Skill",
            "What's the weather like in Seattle today? I'm planning an outdoor hike.");

        // ── Demo 4: Interactive Mode ──
        await RunInteractive(agent);
    }

    /// <summary>
    /// Runs a single demo prompt against the skills-enabled agent.
    /// </summary>
    static async Task RunDemo(AIAgent agent, string demoName, string prompt)
    {
        Console.WriteLine($"━━━ {demoName} ━━━");
        Console.WriteLine($"Prompt: {prompt.Trim()}\n");

        try
        {
            AgentResponse response = await agent.RunAsync(prompt);
            Console.WriteLine($"Response:\n{response.Text}\n");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error: {ex.Message}\n");
        }

        Console.WriteLine(new string('─', 50));
        Console.WriteLine();
    }

    /// <summary>
    /// Interactive chat loop — type questions to interact with the skills-enabled agent.
    /// </summary>
    static async Task RunInteractive(AIAgent agent)
    {
        Console.WriteLine("━━━ Interactive Mode ━━━");
        Console.WriteLine("Type your questions to interact with the skills-enabled agent.");
        Console.WriteLine("The agent has access to: expense-report, code-review, weather-lookup skills.");
        Console.WriteLine("Type 'quit' to exit.\n");

        AgentSession session = await agent.CreateSessionAsync();

        while (true)
        {
            Console.Write("You: ");
            var input = Console.ReadLine();

            if (string.IsNullOrWhiteSpace(input))
                continue;

            if (input.Equals("quit", StringComparison.OrdinalIgnoreCase))
                break;

            try
            {
                AgentResponse response = await agent.RunAsync(input, session);
                Console.WriteLine($"\nAgent: {response.Text}\n");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"\nError: {ex.Message}\n");
            }
        }

        Console.WriteLine("Goodbye!");
    }
}
