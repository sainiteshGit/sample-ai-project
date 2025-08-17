# SemanticKernelMcpSample

A Model Context Protocol (MCP) server that provides intelligent natural language access to Azure Cosmos DB using Semantic Kernel and Azure OpenAI. This project demonstrates how to combine the power of AI with database querying through a clean MCP interface.

## 🎯 Overview

This MCP server allows you to interact with Azure Cosmos DB using natural language queries. Instead of writing complex SQL queries, you can simply ask questions in plain English like "Show me items from Charlotte" or "Find all books under $30", and the server will automatically convert your question to SQL, execute it against Cosmos DB, and return the results.

## ✨ Key Features

- **🤖 Natural Language Queries**: Ask questions in plain English and get SQL results
- **⚡ Automatic SQL Generation**: Converts natural language to optimized Cosmos DB SQL queries using Azure OpenAI
- **🔒 Parameterized Queries**: Safe query execution with parameter binding
- **📊 Structured Results**: Returns results in JSON format with query metadata
- **🛡️ Error Handling**: Robust error handling with informative error messages
- **⚙️ Flexible Configuration**: Easy setup with Azure OpenAI and Cosmos DB

## 🏗️ Architecture

The project uses:
- **Semantic Kernel**: For AI orchestration and Azure OpenAI integration
- **Model Context Protocol (MCP)**: For standardized tool communication
- **Azure Cosmos DB**: As the data store
- **Azure OpenAI**: For natural language to SQL conversion
- **.NET 8**: As the runtime platform

## 🚀 Getting Started

### Prerequisites

- .NET 8 SDK
- Azure OpenAI service with a deployed GPT model
- Azure Cosmos DB account with sample data
- VS Code with GitHub Copilot (recommended)

### Setup

1. **Clone and navigate to the project:**
   ```bash
   cd semantickernel-agent/SemanticKernelMcpSample
   ```

2. **Configure your settings in `Settings.cs`:**
   ```csharp
   public static class Settings
   {
       public static string ChatModelDeployment = "your-gpt-model-deployment";
       public static string Endpoint = "https://your-openai-service.openai.azure.com/";
       public static string ApiKey = "your-api-key";
       public static string AZURE_COSMOS_CONNECTION_STRING = "your-cosmos-connection-string";
       public static string COSMOS_DB = "appdb";
       public static string COSMOS_CONTAINER = "items";
   }
   ```

3. **Install dependencies:**
   ```bash
   dotnet restore
   ```

4. **Build the project:**
   ```bash
   dotnet build
   ```

5. **Run the MCP server:**
   ```bash
   dotnet run
   ```

## 🔧 Available Tools

### 1. `ask_database` - Natural Language Query ⭐ (Primary Tool)

Ask questions in natural language and get intelligent results with automatic SQL generation and execution.

**Parameters:**
- `question` (string): Natural language question about the data
- `database` (string, optional): Database name (default: "appdb")
- `container` (string, optional): Container name (default: "items")
- `maxResults` (int, optional): Maximum number of results to return (default: 20)

**Example Usage:**
```
"Show me items from Charlotte"
"Find all books under $30"
"What electronics are available?"
"List recent items created this month"
```

**Response Format:**
```json
{
  "question": "Show me items from Charlotte",
  "sql": "SELECT TOP 20 * FROM c WHERE c.city = @city",
  "results": [
    {
      "id": "1",
      "category": "books",
      "title": "Clean Code",
      "price": 28.5,
      "city": "Charlotte"
    }
  ],
  "count": 3
}
```

### 2. `query_by_where` - Structured Query

Query Cosmos DB using a WHERE clause without the 'WHERE' keyword. More control than natural language queries.

**Parameters:**
- `database` (string): Database name
- `container` (string): Container name
- `whereClause` (string): WHERE clause (e.g., "c.category = @category AND c.price < @maxPrice")
- `parametersJson` (string, optional): JSON object with parameters (default: "{}")
- `top` (int, optional): Maximum number of items to return (default: 20)

**Example:**
```
whereClause: "c.city = @city"
parametersJson: {"city":"Charlotte"}
```

### 3. `query_sql` - Advanced SQL Query

Execute full SQL queries with parameters. Use with caution for advanced scenarios.

**Parameters:**
- `database` (string): Database name
- `container` (string): Container name
- `sql` (string): Full SQL query
- `parametersJson` (string, optional): JSON object with parameters (default: "{}")

## 📝 Sample Data Structure

The server expects Cosmos DB documents with this structure:
```json
{
  "id": "1",
  "category": "books",
  "title": "Clean Code",
  "price": 28.5,
  "city": "Charlotte",
  "createdAt": "2025-08-01T10:15:00Z"
}
```

## 🔗 MCP Integration

This server implements the Model Context Protocol and can be used with any MCP-compatible client, including:
- GitHub Copilot
- Claude Desktop
- Custom MCP clients

### Adding to VS Code with GitHub Copilot

Add to your MCP configuration:
```json
{
  "mcpServers": {
    "semantickernel": {
      "command": "dotnet",
      "args": ["run", "--project", "/path/to/SemanticKernelMcpSample"],
      "env": {}
    }
  }
}
```

## 💡 How It Works

1. **Question Processing**: The natural language question is sent to Azure OpenAI
2. **SQL Generation**: AI converts the question to a Cosmos DB SQL query with parameters
3. **Parameter Extraction**: Smart parameter extraction from the original question
4. **Query Execution**: Safe execution against Cosmos DB with parameter binding
5. **Result Formatting**: Results returned in structured JSON format

## 🛠️ Technology Stack

- **Framework**: .NET 8
- **AI Platform**: Azure OpenAI via Semantic Kernel
- **Database**: Azure Cosmos DB
- **Protocol**: Model Context Protocol (MCP)
- **Packages**:
  - Microsoft.SemanticKernel (1.45.0)
  - Microsoft.SemanticKernel.Connectors.AzureOpenAI (1.58.0)
  - Microsoft.Azure.Cosmos (3.43.1)
  - ModelContextProtocol (0.3.0-preview.3)

## 🔍 Example Queries

Here are some example natural language queries you can try:

- **Location-based**: "Show me items from Charlotte"
- **Category-based**: "Find all books", "What electronics are available?"
- **Price-based**: "Show items under $50", "Find expensive items over $100"
- **Recent items**: "Show me recent items", "What was added this week?"
- **Combinations**: "Find books in Charlotte under $30"

## 🚧 Error Handling

The server includes comprehensive error handling:
- Invalid SQL generation
- Cosmos DB connection issues
- Parameter binding errors
- Query execution failures

All errors are returned in JSON format with descriptive messages.

## 📄 License

This project is part of the sample-ai-project repository. Please refer to the repository's license for usage terms.

## 🤝 Contributing

This is a sample project demonstrating MCP integration with Semantic Kernel and Cosmos DB. Feel free to use it as a starting point for your own MCP servers.

## 📚 Related Projects

- [MCPSample](../../../MCPSample) - Basic MCP server with weather tools
- [SemanticKernelSampleApp](../SemanticKernelSampleApp) - Semantic Kernel orchestration examples
- [Remote MCP APIM](../../../remote-mcp-apim-appservice-dotnet) - Enterprise MCP deployment pattern
