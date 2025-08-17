using System.ComponentModel;
using System.Text.Json;
using Microsoft.Azure.Cosmos;
using Newtonsoft.Json.Linq;

// Legacy Plugin (for backwards compatibility - keeping Semantic Kernel references removed)
public class CosmosQueryPlugin
{
    private readonly CosmosClient _client;

    public CosmosQueryPlugin(CosmosClient client) => _client = client;

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

        // Create a proper JSON array from the string results
        var jsonArray = "[" + string.Join(",", results) + "]";
        return jsonArray;
        }
        catch (Exception ex)
        {
            return $"{{\"error\": \"Failed to query database: {ex.Message}\"}}";
        }
    }

    [Description("Advanced: run a full SQL query with parameters. Prefer query_by_where for safety.")]
    public async Task<string> QuerySqlAsync(
        [Description("Database name")] string database,
        [Description("Container name")] string container,
        [Description("Full SQL query, e.g., \"SELECT TOP 10 c.id, c.category FROM c WHERE c.city=@city\"")] string sql,
        [Description("JSON object with parameters, e.g., {\"city\":\"Charlotte\"}")] string parametersJson = "{}")
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

        // Create a proper JSON array from the string results
        var jsonArray = "[" + string.Join(",", results) + "]";
        return jsonArray;
    }

    private static QueryDefinition AddParam(QueryDefinition q, string name, JsonElement val)
    {
        return val.ValueKind switch
        {
            JsonValueKind.String => q.WithParameter(name, val.GetString()),
            JsonValueKind.Number => val.TryGetInt64(out var i) ? q.WithParameter(name, i)
                                 : val.TryGetDouble(out var d) ? q.WithParameter(name, d)
                                 : q.WithParameter(name, val.ToString()),
            JsonValueKind.True => q.WithParameter(name, true),
            JsonValueKind.False => q.WithParameter(name, false),
            JsonValueKind.Null => q.WithParameter(name, (object?)null),
            _ => q.WithParameter(name, val.ToString())
        };
    }
}
