using System;
using System.Threading.Tasks;
using Azure.Identity;
using Microsoft.SemanticKernel;
using Microsoft.SemanticKernel.Agents;
using Microsoft.SemanticKernel.ChatCompletion;
using Microsoft.SemanticKernel.Connectors.AzureOpenAI;
using Plugins;
using Microsoft.SemanticKernel.Agents.Orchestration;
using Microsoft.SemanticKernel.Agents.Orchestration.Concurrent;
using Microsoft.SemanticKernel.Agents.Orchestration.Sequential;
using Microsoft.SemanticKernel.Agents.Orchestration.GroupChat;
using Microsoft.SemanticKernel.Agents.Runtime.InProcess;
using Microsoft.SemanticKernel.Agents.Orchestration.Handoff;
namespace SemanticKernelSampleApp;

public static class Program
{
    public static async Task Main()
    {
        // Load configuration from environment variables or user secrets.
        Console.WriteLine("Initialize plugins...");
        MathPlugin mathPlugin = new();
        TaxPlugin taxPlugin = new();

        Console.WriteLine("Creating kernel...");
        IKernelBuilder builder = Kernel.CreateBuilder();

        builder.AddAzureOpenAIChatCompletion(
            deploymentName: Settings.ChatModelDeployment,
            apiKey: Settings.ApiKey,
            endpoint: Settings.Endpoint,
            modelId: Settings.ChatModelDeployment);

        Kernel kernel = builder.Build();

        Console.WriteLine("Defining agent...");

        //###################### Concurrent ORCHESTRATION ######################

        ChatCompletionAgent securityAgent = new ChatCompletionAgent
        {
            Name = "SecurityAuditor",
            Description = "A security expert that reviews code for security flaws, hardcoded secrets, and OWASP Top 10 vulnerabilities.",
            Instructions = @"You are a security expert. Review code for security flaws, hardcoded secrets, and OWASP Top 10 vulnerabilities.
            After your analysis, only provide:
            Summary: A one-sentence summary of your findings.
            Description: A short paragraph (max 120 characters) describing the most important issue or insight.",
            Kernel = kernel,
        };

        ChatCompletionAgent reliabilityAgent = new ChatCompletionAgent
        {
            Name = "ReliabilityAgent",
            Description = "A software reliability engineer that audits code for reliability, fault tolerance, and error handling.",
            Instructions = @"
            You are a software reliability engineer.

            Your task is to audit the given code for reliability issues. Focus on:
            - Fault tolerance and graceful failure handling
            - Use (or absence) of retry, timeout, and circuit breaker patterns
            - How transient errors are managed (e.g., HTTP failures, database timeouts)
            - Logging of failure scenarios
            - Whether the code can recover from partial failures
            - Avoidance of anti-patterns like silent exception swallowing

            Highlight any parts of the code that could lead to service instability under load or network failures.

            Be technical, precise, and suggest improvements.

            After your analysis, only provide:
            Summary: A one-sentence summary of your findings.
            Description: A short paragraph (max 120 characters) describing the most important issue or insight.",
            Kernel = kernel,
        };

        ChatCompletionAgent testingAgent = new ChatCompletionAgent
        {
            Name = "TestCoverageAgent",
            Description = "A testing expert that ensures test coverage and suggests missing test cases.",
            Instructions = @"You are a testing expert. Ensure test coverage is adequate and that edge cases are handled. Suggest missing test cases.
            After your analysis, only provide:
            Summary: A one-sentence summary of your findings.
            Description: A short paragraph (max 120 characters) describing the most important issue or insight.",
            Kernel = kernel,
        };

        ConcurrentOrchestration orchestration = new(securityAgent, testingAgent, reliabilityAgent);

        InProcessRuntime runtime = new InProcessRuntime();
        await runtime.StartAsync();
        string code = @"public async Task<string> GetUserProfileAsync(string userId)
        {
            var apiKey = ""hardcoded-api-key"";

            var client = new HttpClient();
            var response = await client.GetAsync(""https://externalapi.com/user/"" + userId);

            if (response.IsSuccessStatusCode)
            {
                var userData = await response.Content.ReadAsStringAsync();
                return userData;
            }
            else
            {
                return null;
            }
        }";

        var concurrentResult = await orchestration.InvokeAsync(code, runtime);

        string[] output = await concurrentResult.GetValueAsync(TimeSpan.FromSeconds(20));
        Console.WriteLine($"\n\t\t############################## Concurrent Orchestration Result Start #########################\n{string.Join("\n\n", output.Select(text => $"{text}"))}");
        Console.WriteLine("################# Concurrent Orchestration Result End #########################\n");

        //Sequential Orchestration

        ChatHistory history = [];

        ValueTask responseCallback(ChatMessageContent response)
        {
            history.Add(response);
            return ValueTask.CompletedTask;
        }

        SequentialOrchestration sequentialOrchestration = new(securityAgent, testingAgent, reliabilityAgent)
        {
            ResponseCallback = responseCallback,
        };
        var sequentialResult = await sequentialOrchestration.InvokeAsync(code, runtime);

        string sequentialOrcehstrationoutput = await sequentialResult.GetValueAsync(TimeSpan.FromSeconds(20));
        Console.WriteLine($"\n\t\t############################## Sequential Orchestration Result Start #########################\n{string.Join("\n\n", sequentialOrcehstrationoutput)}");
        Console.WriteLine("################# Sequential Orchestration Result End #########################\n");

        //Group Chat Orchestration

        ChatCompletionAgent productOwner = new ChatCompletionAgent
        {
            Name = "ProductOwner",
            Description = "A product owner who clarifies requirements.",
            Instructions = "You are a Product Owner. Expand on the business requirements and clarify any ambiguities. Ask questions if something is unclear, but focus on gathering all necessary details.",
            Kernel = kernel // The LLM connection
        };

        ChatCompletionAgent developer = new ChatCompletionAgent
        {
            Name = "Developer",
            Description = "A developer who breaks down requirements.",
            Instructions = "You are a Developer. Break down the requirements into user stories and technical tasks. Be concise and clear.",
            Kernel = kernel
        };

        ChatCompletionAgent qaAgent = new ChatCompletionAgent
        {
            Name = "QATester",
            Description = "A QA engineer who writes test cases.",
            Instructions = "You are a QA Engineer. Write Gherkin Given/When/Then tests for each user story. When done, finish with 'Test cases complete'. Do not keep asking how to help further.",
            Kernel = kernel
        };

        ChatHistory grouphistory = [];

        ValueTask responseCallbackGroup(ChatMessageContent response)
        {
            grouphistory.Add(response);
            return ValueTask.CompletedTask;
        }

        GroupChatOrchestration groupChatOrchestration = new GroupChatOrchestration(
            new RoundRobinGroupChatManager { MaximumInvocationCount = 15 },
            productOwner,
            developer, qaAgent)
        {
            ResponseCallback = responseCallbackGroup,
        };

        string initialTask = "We need an online grocery ordering system with same-day delivery, secure payments, order tracking, and promo codes.";

        var groupResult = await groupChatOrchestration.InvokeAsync(initialTask, runtime);
        Console.WriteLine($"\n\t\t############################## Group Chat Orchestration Result Start #########################");
        string groupOutput = await groupResult.GetValueAsync(TimeSpan.FromSeconds(120));
        Console.WriteLine($"\n# GROUP CHAT ORCHESTRATION RESULT: {groupOutput}");
        Console.WriteLine("\n\nGROUP CHAT ORCHESTRATION  HISTORY");
        foreach (ChatMessageContent message in grouphistory)
        {
            Console.WriteLine($"{message.Role}: {message.Content}");
        }

        Console.WriteLine("################# Group Chat Orchestration Result End #########################\n");

        //HandOff Orchestration

        ChatCompletionAgent dbAgent = new ChatCompletionAgent
        {
            Name = "DBMitigationAgent",
            Description = "Handles database-related incidents.",
            Instructions = "You specialize in database reliability issues. If the incident is about DB timeouts, propose retries or scaling.",
            Kernel = kernel // The LLM connection
        };

        ChatCompletionAgent netAgent = new ChatCompletionAgent
        {
            Name = "NetworkMitigationAgent",
            Description = "Handles network connectivity problems.",
            Instructions = "You handle network issues like packet loss or high latency. Suggest network failover or CDN fixes.",
            Kernel = kernel // The LLM connection
        };

        ChatCompletionAgent triageAgent = new ChatCompletionAgent
        {
            Name = "TriageAgent",
            Description = "Determines which agent should handle the issue.",
            Instructions = """
                You are a triage AI. Read the incident description and decide:
                - If it's a database-related issue, hand off to DBMitigationAgent
                - If it's a network-related issue, hand off to NetworkMitigationAgent
                - If it's unknown, escalate to HumanEscalationAgent
                Always explain your decision.
                """,
            Kernel = kernel // The LLM connection
        };

        var handoffs = OrchestrationHandoffs
            .StartWith(triageAgent)
            .Add(triageAgent, netAgent, dbAgent)
            .Add(netAgent, triageAgent, "Transfer to this agent if the issue is not related to network connectivity")
            .Add(dbAgent, triageAgent, "Transfer to this agent if the issue is not return related to db connectivity");

        ChatHistory handOffHistory = [];

        ValueTask responseHandOffCallback(ChatMessageContent response)
        {
            handOffHistory.Add(response);
            return ValueTask.CompletedTask;
        }

        // Simulate user input with a queue
        Queue<string> responses = new();
        responses.Enqueue("I'd like to resolve Deployment v2.3.1 failed due to DB connection timeout errors after schema migration.");
        responses.Enqueue("No, I have another issue.");
        responses.Enqueue("I'd like to resolve Deployment v2.3.2 failed due to Network connection unreachable host.");

        ValueTask<ChatMessageContent> interactiveCallback()
        {
            string input = responses.Dequeue();
            Console.WriteLine($"\n# INPUT: {input}\n");
            return ValueTask.FromResult(new ChatMessageContent(AuthorRole.User, input));
        }

        //setup handoff orchestration
        HandoffOrchestration handoffOrchestration = new HandoffOrchestration(
            handoffs,
            triageAgent,
            netAgent,
            dbAgent)
        {
            InteractiveCallback = interactiveCallback,
            ResponseCallback = responseHandOffCallback,
        };

        string task = "I'd like to resolve Deployment v2.3.1 failed due to DB connection timeout errors after schema migration.";
        var handOffResult = await handoffOrchestration.InvokeAsync(task, runtime);

        Console.WriteLine($"\n\n\t\t############################## HandOff Orchestration Result Start #########################");
        string handOffOutput = await handOffResult.GetValueAsync(TimeSpan.FromSeconds(120));
        Console.WriteLine($"\n# HandOff ORCHESTRATION RESULT: {handOffOutput}");
        Console.WriteLine("\n HandOff ORCHESTRATION  HISTORY");
        foreach (ChatMessageContent message in handOffHistory)
        {
            Console.WriteLine($"{message.Role}: {message.Content}");
        }
        Console.WriteLine("################# HandOff Orchestration Result End #########################\n");
        await runtime.RunUntilIdleAsync();
        //Concurrent
        //Sequential
        //GroupChat
        //Magentic One
    }
}