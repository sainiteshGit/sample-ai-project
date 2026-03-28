# Microsoft Agent Framework — Agent Safety Sample

Demonstrates every safety best practice from the [Agent Safety documentation](https://learn.microsoft.com/en-us/agent-framework/agents/safety) with working C# code.

## What This Covers

| Safety Practice | Component | Demo |
|---|---|---|
| Validate function inputs | `InputValidator` | Demo 1 |
| Validate & sanitize LLM output | `OutputSanitizer` | Demo 2 |
| Require approval for high-risk tools | `ApprovalRequiredAIFunction` | Demo 3 |
| Implement resource limits | `ResourceLimiter` | Demo 4 |
| Protect sensitive data in logs | `LogRedactor` | Demo 5 |
| Full pipeline (all guards combined) | `AIAgentBuilder.Use()` middleware | Demo 6 |

## Project Structure

```
msft-agent-framework-safety/
├── Program.cs                               # 6 demos
├── AgentSafetySample.csproj                 # .NET 8
├── appsettings.json                         # Safety configuration
├── Safety/
│   ├── InputValidator.cs                    # Input validation & allow-listing
│   ├── OutputSanitizer.cs                   # XSS/SQL/HTML sanitization
│   ├── ResourceLimiter.cs                   # Rate limiting & length constraints
│   └── LogRedactor.cs                       # PII redaction for logs
└── Tools/
    └── SampleTools.cs                       # Safe + high-risk function tools
```

## Setup

```bash
cd msft-agent-framework-safety
cp appsettings.Development.json.template appsettings.Development.json
# Edit with your Azure OpenAI credentials
dotnet run
```

## Safety Configuration (appsettings.json)

```json
{
  "Safety": {
    "MaxInputLength": 4000,
    "MaxOutputTokens": 2048,
    "RateLimitPerMinute": 10,
    "AllowedFileDirectories": ["./data", "./uploads"],
    "BlockedPatterns": ["<script", "javascript:", "on[a-z]+="],
    "SanitizeHtmlOutput": true,
    "RequireApprovalForTools": ["DeleteRecord", "SendEmail", "ExecuteCommand"]
  }
}
```

## Demos

### Demo 1: Input Validation
- Blocks XSS (`<script>`, `onerror=`) via pattern matching
- Enforces max input length (4000 chars)
- Path traversal prevention with allow-listing (resolves to absolute path, checks against allowed dirs)
- Function argument validation (type, length, path safety)

### Demo 2: Output Sanitization
- Strips dangerous HTML/JS from LLM output using HtmlSanitizer
- Detects and removes `<script>`, `javascript:`, event handlers
- SQL injection pattern scanning for output bound for DB queries
- JSON output validation

### Demo 3: Tool Approval (HITL)
- Auto-approved tools: `LookupCustomer`, `GetWeather` (read-only, no side effects)
- Approval-required tools: `DeleteRecord`, `SendEmail`, `ExecuteCommand` (irreversible, sensitive)
- Uses `ApprovalRequiredAIFunction` + `FunctionApprovalRequestContent` flow
- Demonstrates rejection handling

### Demo 4: Resource Limits
- Input length enforcement
- Sliding-window rate limiter (requests per minute per session)
- `MaxOutputTokens` configuration

### Demo 5: Secure Logging
- Redacts emails, SSNs, credit card numbers, phone numbers, API keys
- Pattern-based with configurable additional patterns
- Shows before/after redaction

### Demo 6: Full Pipeline
- `AIAgentBuilder.Use()` middleware wrapping the agent
- Pre-processing: rate limit → input validation → log redaction
- Post-processing: output sanitization → redacted logging
- Blocked inputs never reach the LLM
