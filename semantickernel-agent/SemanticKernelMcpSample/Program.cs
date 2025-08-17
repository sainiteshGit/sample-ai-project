using Microsoft.Azure.Cosmos;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.SemanticKernel;
using ModelContextProtocol.Server;
using System.ComponentModel;
using System.Text.Json;
using Newtonsoft.Json.Linq;
using static Settings;

var builder = Host.CreateApplicationBuilder(args);

// Configure logging to stderr (for MCP)
builder.Logging.AddConsole(consoleLogOptions =>
{
    consoleLogOptions.LogToStandardErrorThreshold = LogLevel.Trace;
});

// Configure Cosmos DB
var cosmosConn = Settings.AZURE_COSMOS_CONNECTION_STRING;
builder.Services.AddSingleton(new CosmosClient(cosmosConn));

// Configure Semantic Kernel
builder.Services.AddKernel()
    .AddAzureOpenAIChatCompletion(
        deploymentName: Settings.ChatModelDeployment,
        endpoint: Settings.Endpoint,
        apiKey: Settings.ApiKey);

// Add MCP Server with tools
builder.Services
    .AddMcpServer()
    .WithStdioServerTransport()
    .WithTools<CosmosQueryTools>();

await builder.Build().RunAsync();

// MCP Server Tool Implementation
[McpServerToolType]
public class CosmosQueryTools
{
    private readonly CosmosClient _client;
    private readonly Kernel _kernel;

    public CosmosQueryTools(CosmosClient client, Kernel kernel) 
    {
        _client = client;
        _kernel = kernel;
    }

    [McpServerTool(Name = "ask_database")]
    [Description("Ask a natural language question about the database and get intelligent results. Example: 'Show me recent orders', 'Find customers in California', 'What are the most popular products?'")]
    public async Task<string> AskDatabaseAsync(
        [Description("Natural language question about the data")] string question,
        [Description("Database name")] string database = "appdb",
        [Description("Container name")] string container = "items",
        [Description("Maximum number of results to return")] int maxResults = 20)
    {
        try
        {
            // Create a prompt to convert natural language to SQL query
            var prompt = $@"
You are a SQL expert for Azure Cosmos DB. Convert the user's natural language question into a proper SQL query.

Database: {database}
Container: {container}
Question: {question}

Rules:
1. Use 'c' as the alias for the container (FROM c)
2. Always include TOP {maxResults} to limit results
3. Return only the SQL query, no explanations
4. Use parameterized queries when possible with @paramName syntax
5. Common fields might be: id, name, category, price, city, state, date, status, etc.
6. If the question is about 'recent' items, assume there's a date field to order by
7. Always start with SELECT TOP {maxResults}

Examples:
- 'recent orders' → SELECT TOP {maxResults} * FROM c WHERE c.category = 'order' ORDER BY c.date DESC
- 'customers in California' → SELECT TOP {maxResults} * FROM c WHERE c.state = @state
- 'products under $50' → SELECT TOP {maxResults} * FROM c WHERE c.price < @maxPrice

SQL Query:";

            // Get SQL query from AI
            var response = await _kernel.InvokePromptAsync(prompt);
            var sqlQuery = response.ToString().Trim();
            
            // Clean up the response (remove any markdown formatting)
            if (sqlQuery.StartsWith("```sql"))
                sqlQuery = sqlQuery.Substring(6);
            if (sqlQuery.EndsWith("```"))
                sqlQuery = sqlQuery.Substring(0, sqlQuery.Length - 3);
            sqlQuery = sqlQuery.Trim();

            // Extract parameters from the SQL query
            var parameters = ExtractParameters(sqlQuery, question);

            // Execute the query
            var cont = _client.GetContainer(database, container);
            var query = new QueryDefinition(sqlQuery);

            // Add parameters to the query
            foreach (var param in parameters)
            {
                query = query.WithParameter(param.Key, param.Value);
            }

            var results = new List<string>();
            using var iter = cont.GetItemQueryIterator<JObject>(query);
            while (iter.HasMoreResults && results.Count < maxResults)
            {
                var page = await iter.ReadNextAsync();
                foreach (var item in page)
                {
                    var jsonString = item.ToString(Newtonsoft.Json.Formatting.None);
                    results.Add(jsonString);
                    
                    if (results.Count >= maxResults) break;
                }
            }

            var resultJson = $"[{string.Join(",", results)}]";
            return $"{{\"question\": \"{question}\", \"sql\": \"{sqlQuery}\", \"results\": {resultJson}, \"count\": {results.Count}}}";
        }
        catch (Exception ex)
        {
            return $"{{\"error\": \"{ex.Message}\", \"question\": \"{question}\"}}";
        }
    }

    private Dictionary<string, object> ExtractParameters(string sqlQuery, string question)
    {
        var parameters = new Dictionary<string, object>();
        
        // Simple parameter extraction based on common patterns
        if (sqlQuery.Contains("@state"))
        {
            var states = new[] { "california", "ca", "texas", "tx", "new york", "ny", "florida", "fl" };
            foreach (var state in states)
            {
                if (question.ToLower().Contains(state))
                {
                    parameters["@state"] = state == "ca" ? "California" : 
                                         state == "tx" ? "Texas" : 
                                         state == "ny" ? "New York" : 
                                         state == "fl" ? "Florida" : 
                                         char.ToUpper(state[0]) + state.Substring(1);
                    break;
                }
            }
        }
        
        if (sqlQuery.Contains("@maxPrice"))
        {
            var priceMatch = System.Text.RegularExpressions.Regex.Match(question, @"\$?(\d+)");
            if (priceMatch.Success)
            {
                parameters["@maxPrice"] = int.Parse(priceMatch.Groups[1].Value);
            }
        }
        
        if (sqlQuery.Contains("@category"))
        {
            var categories = new[] { "order", "product", "customer", "item", "book", "electronics", "clothing" };
            foreach (var category in categories)
            {
                if (question.ToLower().Contains(category))
                {
                    parameters["@category"] = category;
                    break;
                }
            }
        }

        return parameters;
    }

    [McpServerTool(Name = "query_by_where")]
    [Description("Query Cosmos DB using a WHERE clause without the 'WHERE' keyword. Returns JSON array of items.")]
    public async Task<string> QueryByWhereAsync(
        [Description("Database name")] string database,
        [Description("Container name")] string container,
        [Description("WHERE clause, e.g., \"c.category = @category AND c.price < @maxPrice\"")] string whereClause,
        [Description("JSON object with parameters, e.g., {\"category\":\"books\",\"maxPrice\":25}")] string parametersJson = "{}",
        [Description("Maximum number of items to return")] int top = 20)
    {
        try
        {
            var cont = _client.GetContainer(database, container);
            var sql = $"SELECT TOP {top} * FROM c WHERE {whereClause}";
            var query = new QueryDefinition(sql);

            if (!string.IsNullOrWhiteSpace(parametersJson))
            {
                using var doc = JsonDocument.Parse(parametersJson);
                foreach (var p in doc.RootElement.EnumerateObject())
                {
                    var name = "@" + p.Name;
                    query = AddParam(query, name, p.Value);
                }
            }

            var results = new List<string>();
            using var iter = cont.GetItemQueryIterator<JObject>(query);
            while (iter.HasMoreResults && results.Count < top)
            {
                var page = await iter.ReadNextAsync();
                foreach (var item in page)
                {
                    var jsonString = item.ToString(Newtonsoft.Json.Formatting.None);
                    results.Add(jsonString);
                    
                    if (results.Count >= top) break;
                }
            }

            return $"[{string.Join(",", results)}]";
        }
        catch (Exception ex)
        {
            return $"Error: {ex.Message}";
        }
    }

    [McpServerTool(Name = "query_sql")]
    [Description("Advanced: run a full SQL query with parameters. Prefer query_by_where for safety.")]
    public async Task<string> QuerySqlAsync(
        [Description("Database name")] string database,
        [Description("Container name")] string container,
        [Description("Full SQL query, e.g., \"SELECT TOP 10 c.id, c.category FROM c WHERE c.city=@city\"")] string sql,
        [Description("JSON object with parameters, e.g., {\"city\":\"Charlotte\"}")] string parametersJson = "{}")
    {
        try
        {
            var cont = _client.GetContainer(database, container);
            var query = new QueryDefinition(sql);

            if (!string.IsNullOrWhiteSpace(parametersJson))
            {
                using var doc = JsonDocument.Parse(parametersJson);
                foreach (var p in doc.RootElement.EnumerateObject())
                {
                    var name = "@" + p.Name;
                    query = AddParam(query, name, p.Value);
                }
            }

            var results = new List<string>();
            using var iter = cont.GetItemQueryIterator<JObject>(query);
            while (iter.HasMoreResults)
            {
                var page = await iter.ReadNextAsync();
                foreach (var item in page)
                {
                    var jsonString = item.ToString(Newtonsoft.Json.Formatting.None);
                    results.Add(jsonString);
                }
            }

            return $"[{string.Join(",", results)}]";
        }
        catch (Exception ex)
        {
            return $"Error: {ex.Message}";
        }
    }

    private static QueryDefinition AddParam(QueryDefinition query, string name, JsonElement value)
    {
        return value.ValueKind switch
        {
            JsonValueKind.String => query.WithParameter(name, value.GetString()),
            JsonValueKind.Number => value.TryGetInt32(out var intVal) ? 
                query.WithParameter(name, intVal) : 
                query.WithParameter(name, value.GetDouble()),
            JsonValueKind.True => query.WithParameter(name, true),
            JsonValueKind.False => query.WithParameter(name, false),
            _ => query.WithParameter(name, value.GetRawText())
        };
    }
}
