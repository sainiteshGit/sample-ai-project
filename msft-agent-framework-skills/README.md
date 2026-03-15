# Microsoft Agent Framework — Agent Skills Sample

This sample demonstrates the **Agent Skills** pattern from the [Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/agents/skills?pivots=programming-language-csharp). Agent Skills are portable packages of instructions, scripts, and resources that give agents specialized capabilities and domain expertise.

## How Agent Skills Work

Skills follow a **progressive disclosure** pattern to minimize context usage:

1. **Advertise** (~100 tokens/skill) — Skill names and descriptions are injected into the system prompt so the agent knows what's available.
2. **Load** (< 5,000 tokens) — When a task matches, the agent calls `load_skill` to retrieve full SKILL.md instructions.
3. **Read resources** (as needed) — The agent calls `read_skill_resource` to fetch supplementary files (references, templates, assets).

## Project Structure

```
msft-agent-framework-skills/
├── AgentSkillsSample.csproj        # .NET 8 console app
├── Program.cs                      # Main demo — basic skills setup + interactive mode
├── AdvancedExamples.cs             # Multiple skill dirs + custom system prompt
├── appsettings.json                # Default config
├── appsettings.Development.json.template  # Copy and fill with your credentials
├── README.md
└── skills/                         # Skills directory (discovered by FileAgentSkillsProvider)
    ├── expense-report/             # Expense validation skill
    │   ├── SKILL.md                # Frontmatter + instructions
    │   ├── references/
    │   │   └── POLICY_FAQ.md       # Detailed policy Q&A
    │   └── assets/
    │       └── expense-report-template.md  # Expense report template
    ├── code-review/                # Code review skill
    │   ├── SKILL.md
    │   └── references/
    │       └── CODING_STANDARDS.md
    └── weather-lookup/             # Weather information skill
        ├── SKILL.md
        └── references/
            └── WEATHER_SOURCES.md
```

## Skill Structure

Each skill is a directory containing a `SKILL.md` file with YAML frontmatter:

```yaml
---
name: expense-report
description: File and validate employee expense reports...
license: MIT
metadata:
  author: contoso-finance
  version: "1.0"
---

# Instructions in markdown...
```

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Max 64 chars, lowercase + hyphens. Must match directory name. |
| `description` | Yes | What the skill does + when to use it. Max 1,024 chars. |
| `license` | No | License reference. |
| `compatibility` | No | Environment requirements. |
| `metadata` | No | Arbitrary key-value pairs. |

## Prerequisites

- [.NET 8 SDK](https://dotnet.microsoft.com/download/dotnet/8.0)
- An Azure OpenAI resource with a deployed model (e.g., `gpt-4o-mini`)

## Setup

1. **Clone** and navigate to this directory:
   ```bash
   cd msft-agent-framework-skills
   ```

2. **Configure credentials** — copy the template and fill in your values:
   ```bash
   cp appsettings.Development.json.template appsettings.Development.json
   ```
   
   Edit `appsettings.Development.json`:
   ```json
   {
     "AzureOpenAI": {
       "Endpoint": "https://your-resource.openai.azure.com",
       "ApiKey": "your-api-key",
       "DeploymentName": "gpt-4o-mini"
     }
   }
   ```

   > **Note:** You can omit `ApiKey` to use `DefaultAzureCredential` instead.

3. **Restore packages and run:**
   ```bash
   dotnet restore
   dotnet run
   ```

## What the Demo Does

The sample runs **three automated demos**, each triggering a different skill:

| Demo | Skill Used | Sample Prompt |
|------|-----------|---------------|
| Expense Report | `expense-report` | "Are tips reimbursable? I left a 25% tip on a $80 taxi ride." |
| Code Review | `code-review` | Reviews a C# code snippet with a SQL injection vulnerability |
| Weather Lookup | `weather-lookup` | "What's the weather like in Seattle today?" |

After the demos, it enters **interactive mode** where you can chat freely and see the agent use skills as needed.

## Key Concepts Demonstrated

### Basic Setup (`Program.cs`)
```csharp
var skillsProvider = new FileAgentSkillsProvider(
    skillPath: Path.Combine(AppContext.BaseDirectory, "skills"));

AIAgent agent = openAIClient
    .GetResponsesClient(deploymentName)
    .AsAIAgent(new ChatClientAgentOptions
    {
        Name = "SkillsAgent",
        ChatOptions = new() { Instructions = "You are a helpful assistant." },
        AIContextProviders = [skillsProvider],
    });
```

### Multiple Skill Directories (`AdvancedExamples.cs`)
```csharp
var skillsProvider = new FileAgentSkillsProvider(
    skillPaths: [
        Path.Combine(AppContext.BaseDirectory, "skills"),
        Path.Combine(AppContext.BaseDirectory, "team-skills"),
    ]);
```

### Custom System Prompt (`AdvancedExamples.cs`)
```csharp
var skillsProvider = new FileAgentSkillsProvider(
    skillPath: Path.Combine(AppContext.BaseDirectory, "skills"),
    options: new FileAgentSkillsProviderOptions
    {
        SkillsInstructionPrompt = """
            You have skills available: {0}
            Use `load_skill` to get instructions.
            """
    });
```

## Adding Your Own Skills

1. Create a new directory under `skills/` (e.g., `skills/my-skill/`)
2. Add a `SKILL.md` with YAML frontmatter (the `name` must match the directory name)
3. Optionally add `references/`, `assets/`, or `scripts/` subdirectories
4. Run the app — the `FileAgentSkillsProvider` auto-discovers new skills

## References

- [Agent Skills Documentation](https://learn.microsoft.com/en-us/agent-framework/agents/skills?pivots=programming-language-csharp)
- [Agent Skills Specification](https://agentskills.io/)
- [Context Providers](https://learn.microsoft.com/en-us/agent-framework/agents/conversations/context-providers)
- [Tools Overview](https://learn.microsoft.com/en-us/agent-framework/agents/tools/)
