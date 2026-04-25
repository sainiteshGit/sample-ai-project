namespace SkillsBenchmark;

/// <summary>
/// A fixed set of test prompts used to compare the Baseline agent (all skill
/// content inlined into the system prompt) versus the Skills agent
/// (SKILL.md files loaded on-demand via FileAgentSkillsProvider).
///
/// Mix:
///  - 5 prompts that need exactly one skill
///  - 1 control prompt that needs no skill
///  - 1 multi-skill prompt
/// </summary>
public static class Prompts
{
    /// <summary>
    /// A test case with a prompt and a list of "ground-truth keywords" that should
    /// appear in a correct, policy-aware answer. The keywords come straight from
    /// the corresponding SKILL.md — they are facts a generic LLM cannot know.
    /// Comparison is case-insensitive substring match.
    /// </summary>
    public record TestCase(string Label, string Text, string[] ExpectedKeywords);

    public static readonly IReadOnlyList<TestCase> All =
    [
        // Expense policy: meals domestic limit = $75, receipt required only if > $25,
        // alcohol-without-client is an auto-reject trigger; verdict format APPROVE/NEEDS_FIX/REJECT.
        new("expense_simple",
            "I have a $42 dinner receipt from a domestic trip 12 days ago, no client present. " +
            "Can I expense it? Apply our policy.",
            ExpectedKeywords: ["$75", "APPROVE"]),

        // Refund policy: 20 days = full refund window; "used, no damage" within 30d = 80% refund.
        new("refund_used_item",
            "Order CON-12345678. Customer used the headphones for 20 days, no damage, " +
            "wants a refund. What do we do?",
            ExpectedKeywords: ["80", "30 days"]),

        // Code style: mutable default argument is the famous Python anti-pattern in our guide.
        new("code_review_python",
            "Review this Python: `def add(x, y=[]): y.append(x); return y` " +
            "— flag any issues per our style guide.",
            ExpectedKeywords: ["mutable default", "NEEDS_CHANGES"]),

        // Privacy: email = P1, IP = P1, deletion deadline = 30 days, backups = 90 days.
        new("privacy_deletion",
            "A user emailed asking us to delete all their data. They have an account with " +
            "email + IP logs. What's the classification and deadline?",
            ExpectedKeywords: ["P1", "30 days", "90 days"]),

        // Unit conversion: 175 lb * 0.453592 = 79.3786 kg. Generic LLM gets this right too.
        new("unit_conversion",
            "Convert 175 pounds to kilograms.",
            ExpectedKeywords: ["79.3", "0.453592"]),

        // Control: no policy involved at all. Skill content shouldn't matter here.
        new("control_no_skill",
            "Write a haiku about debugging. No tools or policies needed.",
            ExpectedKeywords: []),

        // Multi-skill: needs expense-policy ($90 < $75 dom meal limit so NEEDS_FIX) AND privacy (P0/P1 for receipt photo).
        new("multi_skill",
            "An employee expensed a $90 client lunch (domestic) AND wants the receipt photo " +
            "deleted from our systems after submission. Address both.",
            ExpectedKeywords: ["$75", "30 days"]),
    ];

    /// <summary>
    /// Crude but objective grounding score: count how many expected keywords
    /// appear in the response (case-insensitive). 0 if no keywords are
    /// expected (control prompt) — reported as N/A.
    /// </summary>
    public static (int hits, int total) Score(TestCase tc, string response)
    {
        if (tc.ExpectedKeywords.Length == 0) return (0, 0);
        int hits = tc.ExpectedKeywords.Count(k =>
            response.Contains(k, StringComparison.OrdinalIgnoreCase));
        return (hits, tc.ExpectedKeywords.Length);
    }
}
