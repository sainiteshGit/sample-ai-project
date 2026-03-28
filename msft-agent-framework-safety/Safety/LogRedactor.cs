using System.Text.RegularExpressions;

namespace AgentSafetySample.Safety;

/// <summary>
/// Guards against PII and sensitive data leaking into logs.
/// Redacts emails, SSNs, credit card numbers, API keys from log output.
/// </summary>
public sealed class LogRedactor
{
    private readonly (Regex Pattern, string Label)[] _redactors;

    /// <summary>
    /// Built-in redaction patterns for common PII.
    /// </summary>
    private static readonly (string Pattern, string Label)[] BuiltInPatterns =
    [
        (@"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "EMAIL"),
        (@"\b\d{3}-\d{2}-\d{4}\b", "SSN"),
        (@"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", "CREDIT_CARD"),
        (@"\b[A-Za-z0-9]{32,}\b", "API_KEY"),  // Long alphanumeric strings (potential keys)
        (@"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "PHONE"),
    ];

    public LogRedactor(string[]? additionalPatterns = null)
    {
        var patterns = new List<(Regex, string)>();

        foreach (var (pattern, label) in BuiltInPatterns)
        {
            patterns.Add((new Regex(pattern, RegexOptions.Compiled), label));
        }

        if (additionalPatterns != null)
        {
            for (int i = 0; i < additionalPatterns.Length; i++)
            {
                patterns.Add((new Regex(additionalPatterns[i], RegexOptions.Compiled), $"CUSTOM_{i}"));
            }
        }

        _redactors = patterns.ToArray();
    }

    /// <summary>
    /// Redacts sensitive data from a string, replacing matches with [REDACTED:LABEL].
    /// </summary>
    public string Redact(string text)
    {
        if (string.IsNullOrEmpty(text))
            return text;

        var result = text;
        foreach (var (pattern, label) in _redactors)
        {
            result = pattern.Replace(result, $"[REDACTED:{label}]");
        }
        return result;
    }

    /// <summary>
    /// Checks if a string contains any sensitive data patterns.
    /// </summary>
    public (bool ContainsSensitiveData, List<string> MatchedCategories) Scan(string text)
    {
        var categories = new List<string>();
        foreach (var (pattern, label) in _redactors)
        {
            if (pattern.IsMatch(text))
            {
                categories.Add(label);
            }
        }
        return (categories.Count > 0, categories);
    }
}
