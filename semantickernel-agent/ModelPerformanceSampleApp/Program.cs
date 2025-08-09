using System;
using System.Threading.Tasks;
using Azure.Identity;
using Microsoft.SemanticKernel;
using Microsoft.SemanticKernel.Agents;
using Microsoft.SemanticKernel.ChatCompletion;
using Microsoft.SemanticKernel.Connectors.AzureOpenAI;
using Microsoft.SemanticKernel.Agents.Orchestration;
using Microsoft.SemanticKernel.Agents.Orchestration.Concurrent;
using Microsoft.SemanticKernel.Agents.Orchestration.Sequential;
using Microsoft.SemanticKernel.Agents.Orchestration.GroupChat;
using Microsoft.SemanticKernel.Agents.Runtime.InProcess;
using Microsoft.SemanticKernel.Agents.Orchestration.Handoff;
using Microsoft.SemanticKernel.Agents.Magentic;
namespace ModelPerformanceSampleApp;

public static class Program
{
    public static async Task Main()
    {
        Console.WriteLine("Starting analysis test...");

        // List of prompts to process
        var prompts = new[]
        {
            /*Variant:: NEW LINE SEPARATED */
            "Summarize the following review and classify its sentiment:\nThe product arrived late but the customer service was excellent and resolved the issue quickly.",
            /*Variant:: ROLE BASED*/
            "You are a helpful assistant. Summarize the following review and classify its sentiment:\nThe product arrived late but the customer service was excellent and resolved the issue quickly.",
            /*Variant:: CHAIN OF THOUGHT CUE*/
            "Think step by step. Summarize the following review and classify its sentiment:\nThe product arrived late but the customer service was excellent and resolved the issue quickly.",  
            /*Variant:: Embedded Context */
            "Customer said: 'The product arrived late but the customer service was excellent and resolved the issue quickly.' What is the sentiment and summary?"  
        };

        // Process each prompt with fresh kernel initialization
        for (int i = 0; i < prompts.Length; i++)
        {
            Console.WriteLine($"\nAnalysis #{i + 1}");
            Console.WriteLine("-------------");
            Console.WriteLine($"Input: {prompts[i]}");
            
            var startTime = DateTime.Now;

            // Initialize new kernel for each prompt
            var builder = Kernel.CreateBuilder();
            builder.AddAzureOpenAIChatCompletion(
                deploymentName: Settings.ChatModelDeployment,
                apiKey: Settings.ApiKey,
                endpoint: Settings.Endpoint,
                modelId: Settings.ChatModelDeployment);
            var newKernel = builder.Build();
            var chatService = newKernel.GetRequiredService<IChatCompletionService>();

            var prompt = prompts[i];
            
            var history = new ChatHistory();
            history.AddUserMessage(prompt);
            var result = await chatService.GetChatMessageContentAsync(history);
            
            var processingTime = (DateTime.Now - startTime).TotalMilliseconds;

            // Print results
            Console.WriteLine($"Output: {result.Content}");
            Console.WriteLine($"Processing Time: {processingTime:F0}ms");
        }

    }
}