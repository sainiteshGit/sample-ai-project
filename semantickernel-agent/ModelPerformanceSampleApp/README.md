# Model Performance Sample App

This application demonstrates performance testing of Azure OpenAI models using Semantic Kernel. It processes multiple prompts and measures the response time for each analysis.

## Features

- Sentiment analysis of text inputs
- Performance measurement in milliseconds
- Individual analysis of multiple prompts
- Fresh kernel initialization for each prompt to ensure isolated testing

## Prerequisites

- .NET 8.0 or later
- Azure OpenAI Service subscription
- Access to GPT models in Azure OpenAI

## Configuration

Update the `Settings.cs` file with your Azure OpenAI credentials:

```csharp
public static string ChatModelDeployment = "your-model-deployment-name";
public static string Endpoint = "your-azure-openai-endpoint";
public static string ApiKey = "your-api-key";
```

## Sample Output

The application processes each prompt and displays:
```
Analysis #1
-------------
Input: [input text]
Output: [analysis result]
Processing Time: XXXms
```

The analysis includes:
1. A brief summary of the input
2. Sentiment classification (Positive/Negative/Mixed)
3. Key points that influenced the sentiment

## Current Test Prompts

The application comes with sample prompts for testing:
1. Customer service experience with late delivery
2. Restaurant review with negative feedback
3. Positive service experience review

## Adding More Test Cases

To add more test cases, modify the `prompts` array in `Program.cs`:

```csharp
var prompts = new[]
{
    "Your new test prompt here",
    // Add more prompts as needed
};
```

## Security Note

- Never commit actual API keys to source control
- Use environment variables or secure configuration management in production
- Rotate API keys regularly

## Dependencies

- Microsoft.SemanticKernel
- Azure.Identity
- Other Semantic Kernel extensions as needed
