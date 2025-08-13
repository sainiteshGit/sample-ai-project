# Semantic Kernel Agent Sample Project

This repository demonstrates advanced orchestration and plugin integration using Microsoft Semantic Kernel in C#. It includes multiple sample apps and plugins for building intelligent agents and measuring model performance.

## Project Structure

- **ModelPerformanceSampleApp/**
  - Performance testing for Azure OpenAI models
  - Measures response time for multiple prompts
  - See `ModelPerformanceSampleApp/README.md` for details
- **SemanticKernelSampleApp/**
  - Demonstrates agent orchestration patterns (Concurrent, Sequential, Group Chat, Handoff, Magentic)
  - Integrates custom plugins (e.g., TaxPlugin, MathPlugin)
  - Example scenarios for multi-agent collaboration
- **Plugins/**
  - Custom plugins for extending agent capabilities
  - Example: `TaxPlugin.cs` for tax calculations

## Key Features

- Multi-agent orchestration using Semantic Kernel
- Custom plugin integration with KernelFunction attributes
- Performance measurement for LLM responses
- Sample scenarios for supply chain, code review, and sentiment analysis

## Getting Started

1. **Clone the repository**
2. **Configure Azure OpenAI credentials**
   - Edit `Settings.cs` in each sample app:
     ```csharp
     public static string ChatModelDeployment = "your-model-deployment-name";
     public static string Endpoint = "your-azure-openai-endpoint";
     public static string ApiKey = "your-api-key";
     ```
3. **Run the sample apps**
   - Use `dotnet run` in each app folder
   - Review console output for analysis results and timings

## Example Output

```
Analysis #1
-------------
Input: The product arrived late but the customer service was excellent and resolved the issue quickly.
Output: [LLM analysis result]
Processing Time: 1234ms
```

## Adding Plugins

- Place new plugin files in the `Plugins/` directory
- Decorate plugin methods with `[KernelFunction]` for automatic registration
- Register plugins in your agent setup code

## Security

- Do NOT commit real API keys to source control
- Use environment variables or secure secrets management in production

## Dependencies

- .NET 8.0+
- Microsoft.SemanticKernel
- Azure.Identity

## References

- [Semantic Kernel Documentation](https://aka.ms/semantic-kernel)
- [Azure OpenAI Service](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/)



### Additional Info
Before proceeding with feature coding, make sure your development environment is fully set up and configured.

Start by creating a Console project. Then, include the following package references to ensure all required dependencies are available.


`dotnet new console -n SemanticKernelSampleApp `


To add package dependencies from the command-line use the dotnet command:



```
dotnet add package Azure.Identity
dotnet add package Microsoft.Extensions.Configuration
dotnet add package Microsoft.Extensions.Configuration.Binder
dotnet add package Microsoft.Extensions.Configuration.UserSecrets
dotnet add package Microsoft.Extensions.Configuration.EnvironmentVariables
dotnet add package Microsoft.SemanticKernel.Connectors.AzureOpenAI
dotnet add package Microsoft.SemanticKernel.Agents.Core --prerelease
dotnet add package Microsoft.SemanticKernel.Agents.Orchestration --prerelease
dotnet add package Microsoft.SemanticKernel.Agents.Runtime.InProcess --prerelease
```


The Agent Framework is experimental and requires warning suppression. This may be addressed in the project file (.csproj):

``` 
<PropertyGroup>
   <NoWarn>$(NoWarn);CA2007;IDE1006;SKEXP0001;SKEXP0110;OPENAI001</NoWarn>
</PropertyGroup>
```

