# MCPSample

This project demonstrates a C#/.NET sample application for interacting with MCP (Model Context Protocol) services. It includes configuration files, HTTP samples, and utility tools for working with weather data and HTTP clients.

## Features

- **WeatherTools:** Utilities for fetching and processing weather data
- **HttpClientExt:** Extensions for HTTP client operations
- **Sample MCP Client:** Example usage of MCP protocol in `Program.cs`
- **App Settings:** Configurable via `appsettings.json` and `appsettings.Development.json`
- **HTTP Samples:** Use `MCPSample.http` for testing API endpoints

## Project Structure

- `Program.cs` — Main entry point for the MCP sample app
- `Tools/WeatherTools.cs` — Weather data utilities
- `Tools/HttpClientExt.cs` — HTTP client extensions
- `MCPSample.http` — HTTP request samples for MCP endpoints
- `appsettings.json` / `appsettings.Development.json` — Configuration files
- `Properties/launchSettings.json` — Launch profiles for development

## Getting Started

1. **Configure settings:**
   - Edit `appsettings.json` and `appsettings.Development.json` as needed
2. **Build and run:**
   - Use `dotnet run` to start the sample app
3. **Test HTTP endpoints:**
   - Use the `MCPSample.http` file with VS Code REST Client or similar tools

## Example Usage

- Fetch weather alerts and forecasts using the provided tools
- Extend the sample to connect to other MCP-compatible services
- Use the HTTP samples to test and debug API interactions

## Extending the Project

- Add new tools to the `Tools/` directory for additional data sources
- Update `Program.cs` to demonstrate new MCP scenarios
- Modify configuration files for different environments

## References

- [Model Context Protocol (MCP)](https://github.com/microsoft/model-context-protocol)
- [.NET Documentation](https://learn.microsoft.com/en-us/dotnet/)


