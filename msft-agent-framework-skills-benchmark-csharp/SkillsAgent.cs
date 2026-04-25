using Azure.AI.OpenAI;
using Microsoft.Agents.AI;
using OpenAI.Responses;

namespace SkillsBenchmark;

/// <summary>
/// Builds the SKILLS agent: a FileAgentSkillsProvider registers SKILL.md files
/// as on-demand context. Only the short skill descriptions sit in the system
/// prompt; full bodies are pulled in via the load_skill tool only when needed.
/// </summary>
public static class SkillsAgentBuilder
{
    public static AIAgent Build(AzureOpenAIClient client, string deployment, string skillsDir)
    {
        var skillsProvider = new FileAgentSkillsProvider(skillPath: skillsDir);

        return client
            .GetResponsesClient(deployment)
            .AsAIAgent(new ChatClientAgentOptions
            {
                Name = "SkillsAgent",
                ChatOptions = new()
                {
                    Instructions =
                        "You are a Contoso operations assistant. Use your available skills " +
                        "when a question matches one. If no skill applies, answer directly.",
                },
                AIContextProviders = [skillsProvider],
            });
    }
}
