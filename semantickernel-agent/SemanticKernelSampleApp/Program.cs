using System;
using System.Threading.Tasks;
using Azure.Identity;
using Microsoft.SemanticKernel;
using Microsoft.SemanticKernel.Agents;
using Microsoft.SemanticKernel.ChatCompletion;
using Microsoft.SemanticKernel.Connectors.AzureOpenAI;
using Plugins;

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

        builder.Plugins.AddFromObject(mathPlugin);
        builder.Plugins.AddFromObject(taxPlugin);

        Kernel kernel = builder.Build();

        Console.WriteLine("Defining agent...");
        ChatCompletionAgent agent =
            new()
            {
                Name = "AssistantAgent",
                Instructions =
                        """
                        You are an agent designed to help users with math and tax calculations.

                        Use the MathPlugin for mathematical operations such as addition, subtraction, multiplication, division, and more.
                        Use the TaxPlugin to help users calculate tax amounts and net income based on their income and tax rate.

                        Use the current date and time to provide up-to-date details or time-sensitive responses.

                        The current date and time is: {{$now}}. 
                        """,
                Kernel = kernel,
                Arguments =
                    new KernelArguments(new AzureOpenAIPromptExecutionSettings() { FunctionChoiceBehavior = FunctionChoiceBehavior.Auto() })
            };

        Console.WriteLine("Ready!");

        ChatHistoryAgentThread agentThread = new();
        bool isComplete = false;
        do
        {
            Console.WriteLine();
            Console.Write("> ");
            string input = Console.ReadLine();
            if (string.IsNullOrWhiteSpace(input))
            {
                continue;
            }
            if (input.Trim().Equals("EXIT", StringComparison.OrdinalIgnoreCase))
            {
                isComplete = true;
                break;
            }

            var message = new ChatMessageContent(AuthorRole.User, input);

            Console.WriteLine();

            DateTime now = DateTime.Now;
            KernelArguments arguments =
                new()
                {
                    { "now", $"{now.ToShortDateString()} {now.ToShortTimeString()}" }
                };
            await foreach (ChatMessageContent response in agent.InvokeAsync(message, agentThread, options: new() { KernelArguments = arguments }))
            {
                // Display response.
                Console.WriteLine($"{response.Content}");
            }

        } while (!isComplete);
    }
}