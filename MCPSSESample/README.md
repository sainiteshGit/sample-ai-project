# MCPSSESample

This project demonstrates a C#/.NET sample application for working with Model Context Protocol (MCP) over Server-Sent Events (SSE). It includes configuration files, a sample SSE transport tool, and an API for integrating with Microsoft Graph and MCP services.

## Features

- **SSE Transport Tool:**
  - `Tools/SampleSSETransportTool.cs` provides utilities for handling SSE connections and events
- **API Integration:**
  - `api/Program.cs` demonstrates connecting to MCP and Microsoft Graph
  - Uses ModelContextProtocol.AspNetCore for MCP server integration
- **Configurable Settings:**
  - `appsettings.json` and `appsettings.Development.json` for environment-specific configuration
- **Solution File:**
  - `src/RemoteMcpMsGraph.sln` for managing the project in Visual Studio

## Project Structure

- `api/Program.cs` — Main entry point for the SSE sample app
- `Tools/SampleSSETransportTool.cs` — SSE transport utilities
- `api/appsettings.json` / `api/appsettings.Development.json` — Configuration files
- `api/RemoteMcpMsGraph.csproj` — Project file
- `Properties/launchSettings.json` — Launch profiles for development

## Getting Started

1. **Configure settings:**
   - Edit `api/appsettings.json` and `api/appsettings.Development.json` as needed
2. **Build and run:**
   - Use `dotnet run` in the `api/` directory to start the sample app
3. **Test SSE endpoints:**
   - Use the SSE transport tool to connect and receive events from the MCP server

## Example Usage

- Connect to MCP server using SSE and receive real-time updates
- Integrate with Microsoft Graph for advanced scenarios
- Extend the sample to support additional event types or protocols

## Extending the Project

- Add new transport tools to the `Tools/` directory
- Update `api/Program.cs` to demonstrate new SSE or MCP scenarios
- Modify configuration files for different environments

## References

- [Model Context Protocol (MCP)](https://github.com/microsoft/model-context-protocol)
- [Server-Sent Events (SSE)](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)
- [Microsoft Graph](https://learn.microsoft.com/en-us/graph/overview)
- [.NET Documentation](https://learn.microsoft.com/en-us/dotnet/)

## License

This project is licensed under the MIT License.
