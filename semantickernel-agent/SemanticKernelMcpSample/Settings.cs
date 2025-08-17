using System.Reflection;
using Microsoft.Extensions.Configuration;

public static class Settings
{
    public static string ChatModelDeployment = "gpt-4.1-mini"; // <REPLACE WITH YOUR MODEL DEPLOYMENT NAME>
    public static string Endpoint = "https://oai-test-learn.openai.azure.com/"; // <REPLACE WITH YOUR ENDPOINT>
    public static string ApiKey = "<REPLACE WITH YOUR API KEY>"; // <REPLACE WITH YOUR API KEY>

    public static string AZURE_COSMOS_CONNECTION_STRING = "<REPLACE WITH YOUR COSMOS CONNECTION STRING>"; // <REPLACE WITH YOUR COSMOS CONNECTION STRING>
    public static string COSMOS_DB = "<REPLACE WITH YOUR COSMOS DB NAME>"; // <REPLACE WITH YOUR COSMOS DB NAME>
    public static string COSMOS_CONTAINER = "<REPLACE WITH YOUR COSMOS CONTAINER NAME>"; // <REPLACE WITH YOUR COSMOS CONTAINER NAME>
}