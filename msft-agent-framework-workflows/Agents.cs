using System.ClientModel;
using Azure.AI.OpenAI;
using Azure.Identity;
using Microsoft.Agents.AI;
using OpenAI.Responses;

namespace WorkflowsBenchmark;

/// <summary>
/// Three single-purpose agents that we wire together in different orchestration
/// patterns. Each agent has a small, well-scoped instruction so we can see what
/// happens when responsibilities are split across agents vs jammed into one.
/// </summary>
internal static class Agents
{
    public static AzureOpenAIClient CreateClient(string endpoint, string? apiKey) =>
        string.IsNullOrWhiteSpace(apiKey)
            ? new AzureOpenAIClient(new Uri(endpoint), new DefaultAzureCredential())
            : new AzureOpenAIClient(new Uri(endpoint), new ApiKeyCredential(apiKey));

    public static AIAgent CreateParser(AzureOpenAIClient client, string deployment) =>
        client.GetResponsesClient(deployment).AsAIAgent(new ChatClientAgentOptions
        {
            Name = "RequestParser",
            ChatOptions = new()
            {
                Instructions =
                    "You parse a free-form travel reimbursement request into a structured " +
                    "summary. Output ONLY these fields, one per line, no commentary:\n" +
                    "  AMOUNT: <number in USD>\n" +
                    "  CATEGORY: <meal | hotel | airfare | other>\n" +
                    "  TRIP_TYPE: <domestic | international>\n" +
                    "  DAYS_AGO: <integer>\n" +
                    "  CLIENT_PRESENT: <true | false>\n" +
                    "Do not approve, reject, or comment. Extraction only.",
            },
        });

    public static AIAgent CreatePolicyChecker(AzureOpenAIClient client, string deployment) =>
        client.GetResponsesClient(deployment).AsAIAgent(new ChatClientAgentOptions
        {
            Name = "PolicyChecker",
            ChatOptions = new()
            {
                Instructions =
                    "You apply Contoso travel reimbursement policy to a parsed request.\n" +
                    "POLICY:\n" +
                    "  Domestic meal cap: $75 (without client) / $150 (with client).\n" +
                    "  International meal cap: $100 / $200.\n" +
                    "  Hotel cap: $250/night domestic, $400/night international.\n" +
                    "  Submission window: 30 days. Older receipts are REJECTED.\n" +
                    "Output exactly two lines:\n" +
                    "  VERDICT: <APPROVE | REJECT | NEEDS_FIX>\n" +
                    "  REASON: <one short sentence citing the specific rule and dollar amount>\n" +
                    "Do not draft an email. Verdict only.",
            },
        });

    public static AIAgent CreateEmailDrafter(AzureOpenAIClient client, string deployment) =>
        client.GetResponsesClient(deployment).AsAIAgent(new ChatClientAgentOptions
        {
            Name = "EmailDrafter",
            ChatOptions = new()
            {
                Instructions =
                    "You draft a short, professional reimbursement decision email to the employee. " +
                    "Use the verdict and reason from the prior policy step verbatim. " +
                    "Keep it under 80 words. Sign as 'Contoso Travel Operations'. " +
                    "Do NOT change the verdict or invent new policy.",
            },
        });

    public static AIAgent CreateMonolithic(AzureOpenAIClient client, string deployment) =>
        client.GetResponsesClient(deployment).AsAIAgent(new ChatClientAgentOptions
        {
            Name = "MonolithicAgent",
            ChatOptions = new()
            {
                Instructions =
                    "You are Contoso's travel reimbursement assistant. For every user request, " +
                    "you must do ALL of the following in one response:\n" +
                    "  1. Parse the request into structured fields (AMOUNT, CATEGORY, TRIP_TYPE, " +
                    "DAYS_AGO, CLIENT_PRESENT).\n" +
                    "  2. Apply policy and decide VERDICT (APPROVE | REJECT | NEEDS_FIX) with REASON.\n" +
                    "  3. Draft a short professional decision email to the employee.\n\n" +
                    "POLICY:\n" +
                    "  Domestic meal cap: $75 (without client) / $150 (with client).\n" +
                    "  International meal cap: $100 / $200.\n" +
                    "  Hotel cap: $250/night domestic, $400/night international.\n" +
                    "  Submission window: 30 days. Older receipts are REJECTED.\n\n" +
                    "Output the parsed fields, then VERDICT + REASON, then the email. " +
                    "Sign the email as 'Contoso Travel Operations'.",
            },
        });
}
