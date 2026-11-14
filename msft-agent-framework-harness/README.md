# Agent harness: shopping assistant

This C# sample follows the shopping-assistant example from the blog. It uses
Microsoft Agent Framework's actual `HarnessAgent` to drive a model/tool loop:

1. The model proposes `SearchProducts`; the harness invokes the local tool.
2. The model proposes `AddToWishlist`; the harness returns an approval request
   instead of executing it.
3. The console collects your decision and resumes the **same session**.
4. The harness executes the tool only when approved and returns the result to
   the model. The program displays the actual in-memory wishlist.

The catalog and wishlist are local demo data; no real store is contacted and
the wishlist disappears when the process exits. The fixed prompt asks for the
laptop with the most RAM strictly under $1,000.

## Run with Azure AI Foundry

Requires the .NET 8 SDK or later and an Azure AI Foundry deployment that
supports the Responses API and function calling. In VS Code, open
**Terminal > New Terminal** in the `msft-agent-framework-harness` folder.
If your terminal is at the repository root, first run
`cd msft-agent-framework-harness`.

Copy `appsettings.Development.json.template` to `appsettings.Development.json`
if you do not already have a local settings file. Set the Azure OpenAI v1 base
endpoint (ending in `/openai/v1/`), deployment name, and API key in its
`AzureOpenAI` section. The local settings file is gitignored; do not put real
keys in the tracked `appsettings.json` or template.

The key is stored in plaintext and copied to the ignored build output by
`dotnet run`. Limit access to those files; use a secure credential provider
instead for production.

Run the app:

```sh
dotnet run
```

Alternatively, set `AZURE_OPENAI_API_KEY` in your environment or enter a key
at the hidden terminal prompt when neither setting is present. The endpoint
and deployment can be overridden with `AZURE_OPENAI_ENDPOINT` and
`AZURE_OPENAI_DEPLOYMENT`. Environment variables take precedence over the
local settings file. `--live` is an explicit alias for the default mode.

The program sends the prompt, tool definitions, and subsequent tool results to
the configured deployment using the Azure OpenAI-compatible
Responses API. It prints each model request and proposed function call. Live
model behavior and the number of calls can vary, and model requests may incur
charges. The framework executes local functions; the console collects approval
before executing the approval-marked wishlist tool.

Enter `y` to approve, or `n` to deny. End-of-input stops the program without
submitting pending approvals. A plain tool is not automatically
approval-protected just because a harness is used.

To keep the example focused, todo tracking, plan/execute modes, file memory,
skills, web search, and the standing/automatic approval middleware are disabled.
The wishlist tool still explicitly requires approval. Compaction is not
configured. This is a learning sample, not a production security boundary or
persistent service.

## References

- [Microsoft Agent Framework: Agent Harness](https://learn.microsoft.com/en-us/agent-framework/concepts/harness?pivots=programming-language-csharp)
- [Tool approval with Harness Agent](https://learn.microsoft.com/en-us/agent-framework/agents/tools/tool-approval?pivots=programming-language-csharp#use-tool-approval-with-harness-agent)
