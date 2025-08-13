# sample-ai-project

This repository contains a collection of advanced C#/.NET sample applications and tools for working with AI, Model Context Protocol (MCP), Semantic Kernel, and Azure OpenAI. Each folder demonstrates a unique scenario, orchestration pattern, or integration technique for building intelligent, multi-agent systems and testing model performance.

## Repository Structure

- **MCPSample/**
  - C# sample for interacting with MCP services
  - Weather and HTTP client utilities
  - HTTP request samples and configuration files
- **MCPSSESample/**
  - SSE (Server-Sent Events) sample for MCP
  - Microsoft Graph integration
  - SSE transport tool and API project
- **semantickernel-agent/**
  - Multiple sample apps for Semantic Kernel agent orchestration and plugin integration
  - Includes:
    - **ModelPerformanceSampleApp/**: Performance testing for Azure OpenAI models
    - **SemanticKernelSampleApp/**: Multi-agent orchestration patterns and plugin demos
    - **Plugins/**: Custom plugins for extending agent capabilities
- **multi-agent/**
  - Example agents and utilities for multi-agent scenarios
  - Includes content generation and travel guide samples


## Key Features

- Multi-agent orchestration using Semantic Kernel
- Custom plugin integration
- Performance measurement for LLM responses
- MCP protocol and SSE integration
- Azure OpenAI and Microsoft Graph connectivity

## Getting Started

1. **Clone the repository**
2. **Configure credentials and settings in each sample app**
3. **Build and run individual projects using `dotnet run`**
4. **Review README files in each folder for specific instructions and scenarios**

## Security

- Do NOT commit real API keys or secrets to source control
- Use environment variables or secure secrets management in production

## References

- [Semantic Kernel Documentation](https://aka.ms/semantic-kernel)
- [Model Context Protocol (MCP)](https://github.com/microsoft/model-context-protocol)
- [Azure OpenAI Service](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/)
- [Microsoft Graph](https://learn.microsoft.com/en-us/graph/overview)
- [.NET Documentation](https://learn.microsoft.com/en-us/dotnet/)

