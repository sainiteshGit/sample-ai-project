using System.ClientModel;
using Azure.AI.OpenAI;
using Azure.Identity;
using Microsoft.Agents.AI;
using Microsoft.Extensions.Configuration;
using OpenAI.Responses;

namespace AgentSkillsSample;

/// <summary>
/// Demonstrates advanced Agent Skills patterns:
///   - Multiple skill directories
///   - Custom system prompt for skills
/// </summary>
class AdvancedExamples
{
    /// <summary>
    /// Example: Loading skills from multiple directories.
    /// Useful when skills come from different teams or repos.
    /// </summary>
    static AIAgent CreateAgentWithMultipleSkillPaths(AzureOpenAIClient openAIClient, string deploymentName)
    {
        // Search multiple directories — each can contain individual skills or parent folders
        var skillsProvider = new FileAgentSkillsProvider(
            skillPaths: [
                Path.Combine(AppContext.BaseDirectory, "skills"),         // Built-in skills
                Path.Combine(AppContext.BaseDirectory, "team-skills"),    // Team-specific skills
            ]);

        return openAIClient
            .GetResponsesClient(deploymentName)
            .AsAIAgent(new ChatClientAgentOptions
            {
                Name = "MultiSkillAgent",
                ChatOptions = new()
                {
                    Instructions = "You are a helpful assistant with access to specialized skills.",
                },
                AIContextProviders = [skillsProvider],
            });
    }

    /// <summary>
    /// Example: Customizing the system prompt that lists available skills.
    /// The {0} placeholder is replaced with the skill list at runtime.
    /// </summary>
    static AIAgent CreateAgentWithCustomPrompt(AzureOpenAIClient openAIClient, string deploymentName)
    {
        var skillsProvider = new FileAgentSkillsProvider(
            skillPath: Path.Combine(AppContext.BaseDirectory, "skills"),
            options: new FileAgentSkillsProviderOptions
            {
                SkillsInstructionPrompt = """
                    You have the following specialized skills available:
                    {0}
                    
                    When a user's request matches a skill domain:
                    1. Use `load_skill` to retrieve the full skill instructions.
                    2. Use `read_skill_resource` to access supplementary files when needed.
                    3. Follow the skill's response format guidelines.
                    
                    Always prefer using a skill over generic knowledge when one is relevant.
                    """
            });

        return openAIClient
            .GetResponsesClient(deploymentName)
            .AsAIAgent(new ChatClientAgentOptions
            {
                Name = "CustomPromptAgent",
                ChatOptions = new()
                {
                    Instructions = "You are a precise, detail-oriented assistant.",
                },
                AIContextProviders = [skillsProvider],
            });
    }
}
