# ----- Build stage -----
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

# Copy csproj and restore first (better layer caching)
COPY AcaMcpServer.csproj ./
RUN dotnet restore AcaMcpServer.csproj

# Copy the rest and publish
COPY . .
RUN dotnet publish AcaMcpServer.csproj -c Release -o /app/publish --no-restore

# ----- Runtime stage -----
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app
COPY --from=build /app/publish ./

# Azure Container Apps injects $PORT (defaults to 8080). Program.cs honors it.
ENV ASPNETCORE_URLS=http://+:8080
EXPOSE 8080

ENTRYPOINT ["dotnet", "AcaMcpServer.dll"]
