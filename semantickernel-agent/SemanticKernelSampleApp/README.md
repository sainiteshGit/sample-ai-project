# SemanticKernelSampleApp

This sample app demonstrates advanced agent orchestration and plugin integration using Microsoft Semantic Kernel in C#. It showcases multiple orchestration patterns and custom plugins for building intelligent, multi-agent systems.

## Features

- **Multi-Agent Orchestration Patterns:**
  - Concurrent
  - Sequential
  - Group Chat
  - Handoff
  - Magentic (advanced triage and collaboration)
- **Custom Plugins:**
  - MathPlugin: Provides math operations
  - TaxPlugin: Calculates tax and demonstrates user-centric plugin design
- **Sample Outputs:**
  - See `GroupChatSampleOutput.md`, `HandOffOrchestrationOutput.md`, and `MagenticOrchestrationOutput.md` for real orchestration results

## How It Works

- Agents are defined in `Program.cs` with clear roles and instructions
- Plugins are registered and exposed via KernelFunction attributes
- Orchestration patterns are demonstrated with real-world scenarios (e.g., supply chain disruption, code review, requirements gathering)
- Each orchestration prints its result and full chat history for transparency

## Getting Started

1. **Configure Azure OpenAI credentials**
   - Edit `Settings.cs`:
     ```csharp
     public static string ChatModelDeployment = "your-model-deployment-name";
     public static string Endpoint = "your-azure-openai-endpoint";
     public static string ApiKey = "your-api-key";
     ```
2. **Run the app**
   - Use `dotnet run` in this folder
   - Review console output and sample output files for orchestration results

## Example Orchestration Patterns

- **Concurrent:** Multiple agents analyze the same input in parallel
- **Sequential:** Agents process input in a defined order, passing results along
- **Group Chat:** Agents collaborate in a round-robin fashion to solve complex tasks
- **Handoff:** Incidents are routed to the right specialist agent based on triage logic
- **Magentic:** Advanced scenario with dynamic agent collaboration and triage

## Adding Plugins

- Place new plugin files in the `Plugins/` directory
- Decorate plugin methods with `[KernelFunction]` for automatic registration
- Register plugins in `Program.cs`

## Security

- Do NOT commit real API keys to source control
- Use environment variables or secure secrets management in production

## References

- [Semantic Kernel Documentation](https://aka.ms/semantic-kernel)
- [Azure OpenAI Service](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/)

## License

This project is licensed under the MIT License.
