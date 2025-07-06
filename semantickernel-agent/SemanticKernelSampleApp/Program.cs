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
using Microsoft.SemanticKernel.Agents.Runtime.InProcess;
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


        await runtime.RunUntilIdleAsync();



        //Concurrent
        //Sequential
        //GroupChat
        //Magentic One
    }
}