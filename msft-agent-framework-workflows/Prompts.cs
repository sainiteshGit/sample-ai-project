namespace WorkflowsBenchmark;

/// <summary>
/// Test prompts for the travel reimbursement pipeline.
/// ExpectedKeywords are POLICY-SPECIFIC facts the agent can only know if it
/// actually applied the rules — e.g. the right verdict word, the right cap,
/// the right rejection reason. Hallucinations score zero.
/// </summary>
internal static class Prompts
{
    public record TestCase(string Label, string Text, string[] ExpectedKeywords);

    public static readonly TestCase[] All =
    {
        // Clear approve — under domestic meal cap, recent, no client.
        new("approve_simple_meal",
            "I'd like to expense a $42 dinner from a domestic trip 12 days ago. " +
            "No client was present.",
            ["APPROVE", "$75"]),

        // Reject — over the domestic meal cap without a client present.
        new("reject_over_meal_cap",
            "Please reimburse a $120 dinner from my domestic trip last week. " +
            "I was alone — no client.",
            ["REJECT", "$75"]),

        // Approve — international with client, under the $200 cap.
        new("approve_intl_with_client",
            "Submitting a $180 dinner from my London trip 5 days ago. " +
            "Two clients were with me.",
            ["APPROVE", "$200"]),

        // Reject — older than the 30-day submission window.
        new("reject_stale",
            "I have a $40 lunch receipt from a domestic trip 45 days ago, no client.",
            ["REJECT", "30 days"]),

        // Reject — hotel rate over the domestic per-night cap.
        new("reject_hotel_over_cap",
            "Need to expense $310/night for 2 nights at a domestic conference last week.",
            ["REJECT", "$250"]),

        // Approve — hotel under international per-night cap.
        new("approve_intl_hotel",
            "Hotel was $380/night for 3 nights in Tokyo 10 days ago.",
            ["APPROVE", "$400"]),
    };

    public static (int hits, int total) Score(TestCase tc, string response)
    {
        if (tc.ExpectedKeywords.Length == 0) return (0, 0);
        int hits = tc.ExpectedKeywords.Count(k =>
            response.Contains(k, StringComparison.OrdinalIgnoreCase));
        return (hits, tc.ExpectedKeywords.Length);
    }
}
