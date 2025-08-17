# Cosmos DB MCP Server with Natural Language Query

This is a Model Context Protocol (MCP) server that provides intelligent natural language access to Azure Cosmos DB using Semantic Kernel and Azure OpenAI. The server is built using the official [ModelContextProtocol C# SDK](https://github.com/modelcontextprotocol/csharp-sdk).

## 🎯 Key Features

### 1. **Natural Language Database Queries** ⭐ NEW!
- Ask questions in plain English like "Show me recent orders" or "Find customers in California"
- Automatically converts natural language to SQL queries using Azure OpenAI
- Executes queries against Cosmos DB and returns actual results
- No need to write SQL - just ask what you want to know!

### 2. **Advanced Query Tools**
- **query_by_where**: Query Cosmos DB using a WHERE clause (safer, recommended)
- **query_sql**: Execute full SQL queries with parameters (advanced usage)

## Tools Available

### `ask_database` - Natural Language Query (Primary Tool) ⭐
Ask questions in natural language and get intelligent results with automatic SQL generation and execution.

**Parameters:**
- `question` (string): Natural language question about the data
- `database` (string, optional): Database name (default: "appdb")
- `container` (string, optional): Container name (default: "items")
- `maxResults` (int, optional): Maximum number of results (default: 20)

**Examples:**
```
"Show me recent orders"
"Find customers in California"  
"What products cost less than $50?"
"List items in the electronics category"
"Show me all books"
```

**Response Format:**
```json
{
  "question": "Show me recent orders",
  "sql": "SELECT TOP 20 * FROM c WHERE c.category = 'order' ORDER BY c.date DESC",
  "results": [...actual data from Cosmos DB...],
  "count": 15
}
```

### query_by_where
Query Cosmos DB using a WHERE clause without the 'WHERE' keyword.

**Parameters:**
- `database` (string): Database name
- `container` (string): Container name  
- `whereClause` (string): WHERE clause, e.g., "c.category = @category AND c.price < @maxPrice"
- `parametersJson` (string, optional): JSON object with parameters, e.g., {"category":"books","maxPrice":25}
- `top` (int, optional): Maximum number of items to return (default: 20)

**Example:**
```json
{
  "database": "MyDatabase",
  "container": "MyContainer", 
  "whereClause": "c.city = @city",
  "parametersJson": "{\"city\":\"Charlotte\"}",
  "top": 10
}
```

### query_sql
Advanced: Run a full SQL query with parameters. Prefer query_by_where for safety.

**Parameters:**
- `database` (string): Database name
- `container` (string): Container name
- `sql` (string): Full SQL query, e.g., "SELECT TOP 10 c.id, c.category FROM c WHERE c.city=@city"
- `parametersJson` (string, optional): JSON object with parameters, e.g., {"city":"Charlotte"}

## Configuration

The server reads configuration from the `Settings` class which should contain:

### Azure Cosmos DB Settings
- `AZURE_COSMOS_CONNECTION_STRING`: Your Cosmos DB connection string
- `COSMOS_DB`: Your database name (default: "appdb")
- `COSMOS_CONTAINER`: Your container name (default: "items")

### Azure OpenAI Settings (for Natural Language Query)
- `ChatModelDeployment`: Your Azure OpenAI model deployment name (e.g., "gpt-4")
- `Endpoint`: Your Azure OpenAI endpoint URL
- `ApiKey`: Your Azure OpenAI API key
- `COSMOS_DB`: Default database name
- `COSMOS_CONTAINER`: Default container name

## Running the Server

```bash
dotnet run
```

The server will start and listen for MCP protocol messages via stdin/stdout.

## MCP Client Integration

This server can be used with any MCP-compatible client. The tools will be automatically discovered and can be invoked using the standard MCP protocol.

## Example Usage

### Natural Language Queries (Recommended)

Simply ask questions in plain English:

1. **"Show me recent orders"**
   - Automatically generates: `SELECT TOP 20 * FROM c WHERE c.category = 'order' ORDER BY c.date DESC`
   - Executes query and returns actual order data

2. **"Find customers in California"**
   - Automatically generates: `SELECT TOP 20 * FROM c WHERE c.state = @state`
   - Automatically detects "California" as the state parameter
   - Returns actual customer records

3. **"What products cost less than $50?"**
   - Automatically generates: `SELECT TOP 20 * FROM c WHERE c.price < @maxPrice`
   - Detects "$50" and sets @maxPrice parameter
   - Returns matching products with pricing data

### Traditional Query Examples

1. **Find books in Charlotte:**
   ```json
   {
     "tool": "query_by_where",
     "parameters": {
       "database": "MyDatabase",
       "container": "MyContainer",
       "whereClause": "c.category = @category AND c.city = @city",
       "parametersJson": "{\"category\":\"books\",\"city\":\"Charlotte\"}"
     }
   }
   ```

2. **Get top 5 electronics:**
   ```json
   {
     "tool": "query_sql", 
     "parameters": {
       "database": "MyDatabase",
       "container": "MyContainer",
       "sql": "SELECT TOP 5 c.id, c.name, c.price FROM c WHERE c.category = @category ORDER BY c.price DESC",
       "parametersJson": "{\"category\":\"electronics\"}"
     }
   }
   ```

## Migration from Custom Implementation

This server replaces the previous custom HTTP SSE implementation with the official MCP SDK. The tools and functionality remain the same, but now use the standardized MCP protocol for better compatibility and integration with MCP clients.

## Dependencies

- Microsoft.Azure.Cosmos 3.43.1
- ModelContextProtocol 0.3.0-preview.3
- Microsoft.Extensions.Hosting 9.0.8
- Newtonsoft.Json 13.0.3
