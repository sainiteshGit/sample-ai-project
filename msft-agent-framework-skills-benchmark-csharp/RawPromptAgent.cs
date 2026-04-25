using Azure.AI.OpenAI;
using Microsoft.Agents.AI;
using OpenAI.Responses;

namespace SkillsBenchmark;

/// <summary>
/// Builds the RAW-PROMPT agent: every SKILL.md file is read as a string,
/// concatenated, and shoved straight into the agent's system Instructions.
/// No tools. No providers. Just a giant string in the prompt, sent on every
/// turn. This is the naive pattern that progressive disclosure replaces.
/// </summary>
public static class RawPromptAgentBuilder
{
    public static AIAgent Build(AzureOpenAIClient client, string deployment, string skillsDir)
    {
        // 1. Read every SKILL.md from disk.
        // 2. Concatenate them into one big string with === SKILL: name === separators.
        // 3. Assign that string to ChatOptions.Instructions (the system prompt).
        string instructions = LoadAllSkillBodies(skillsDir);

        return client
            .GetResponsesClient(deployment)
            .AsAIAgent(new ChatClientAgentOptions
            {
                Name = "RawPromptAgent",
                ChatOptions = new()
                {
                    Instructions = instructions,
                },
            });
    }

    public static string LoadAllSkillBodies(string skillsDir)
    {
        var sb = new System.Text.StringBuilder();
        sb.AppendLine("You are a Contoso operations assistant. The sections below contain ALL " +
                      "the policies and references you must apply. Choose the right section for " +
                      "each user question.");

        foreach (string skillMd in Directory
                     .EnumerateFiles(skillsDir, "SKILL.md", SearchOption.AllDirectories)
                     .OrderBy(p => p))
        {
            string skillName = Path.GetFileName(Path.GetDirectoryName(skillMd)!);
            sb.AppendLine();
            sb.AppendLine($"===== SKILL: {skillName} =====");
            sb.AppendLine(File.ReadAllText(skillMd));
        }

        return sb.ToString();
    }
}
