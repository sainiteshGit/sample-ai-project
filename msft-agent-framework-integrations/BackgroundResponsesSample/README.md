# Background Responses Sample - Microsoft Agent Framework

Demonstrates background responses with continuation tokens using the Microsoft Agent Framework's OpenAI Responses API integration.

## What This Demonstrates

- **Non-Streaming (Polling)**: Send a complex prompt, receive a continuation token, and poll until the response is ready
- **Streaming (Resumable)**: Stream responses in real-time with the ability to resume from an interruption point
- **Interactive Chat**: Free-form conversation with background response support

## Prerequisites

- .NET 8.0 SDK
- Azure OpenAI resource with a deployed model
- Azure CLI authenticated (`az login`) for `DefaultAzureCredential`

## Setup

1. Copy `appsettings.Development.json.template` to `appsettings.Development.json`
2. Update the Azure OpenAI endpoint and deployment name
3. Ensure you're authenticated with Azure CLI

```bash
az login
```

## Run

```bash
dotnet run
```

## Key Concepts

### Background Responses
When an agent needs more time to process a complex request, it returns a **continuation token** instead of the final response. You then poll with this token until the operation completes (`ContinuationToken` becomes `null`).

### Continuation Tokens
- Contain all state needed to resume or poll for results
- Can be persisted for operations spanning user sessions
- `null` token = operation complete

### Important
Background responses **only work with OpenAI Responses API agents** (not `ChatClientAgent`). The agent is created via:
```csharp
.GetResponsesClient(deploymentName).AsAIAgent(...)
```

## References

- [Background Responses Documentation](https://learn.microsoft.com/en-us/agent-framework/agents/background-responses?pivots=programming-language-csharp)
- [Agent Framework Samples](https://github.com/microsoft/agent-framework/tree/main/dotnet/samples)
