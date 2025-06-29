Before proceeding with feature coding, make sure your development environment is fully set up and configured.

Start by creating a Console project. Then, include the following package references to ensure all required dependencies are available.


`dotnet new console -n SemanticKernelSampleApp `


To add package dependencies from the command-line use the dotnet command:



```
dotnet add package Azure.Identity
dotnet add package Microsoft.Extensions.Configuration
dotnet add package Microsoft.Extensions.Configuration.Binder
dotnet add package Microsoft.Extensions.Configuration.UserSecrets
dotnet add package Microsoft.Extensions.Configuration.EnvironmentVariables
dotnet add package Microsoft.SemanticKernel.Connectors.AzureOpenAI
dotnet add package Microsoft.SemanticKernel.Agents.Core --prerelease
```


The Agent Framework is experimental and requires warning suppression. This may be addressed in the project file (.csproj):

``` 
<PropertyGroup>
   <NoWarn>$(NoWarn);CA2007;IDE1006;SKEXP0001;SKEXP0110;OPENAI001</NoWarn>
</PropertyGroup>
```

