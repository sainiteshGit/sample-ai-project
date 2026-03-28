using System.Text.RegularExpressions;
using Ganss.Xss;

namespace AgentSafetySample.Safety;

/// <summary>
/// Sanitizes LLM output before it reaches the user or downstream systems.
/// Prevents XSS, injection attacks, and validates output structure.
/// </summary>
public sealed class OutputSanitizer
{
    private readonly HtmlSanitizer _htmlSanitizer;
    private readonly bool _sanitizeHtml;

    // Patterns that should never appear in LLM output destined for rendering
    private static readonly Regex[] DangerousPatterns =
    [
        new(@"<script[\s>]", RegexOptions.IgnoreCase | RegexOptions.Compiled),
        new(@"javascript\s*:", RegexOptions.IgnoreCase | RegexOptions.Compiled),
        new(@"on\w+\s*=", RegexOptions.IgnoreCase | RegexOptions.Compiled),
        new(@"data\s*:\s*text/html", RegexOptions.IgnoreCase | RegexOptions.Compiled),
        new(@"vbscript\s*:", RegexOptions.IgnoreCase | RegexOptions.Compiled),
    ];

    // SQL injection indicators
    private static readonly Regex[] SqlPatterns =
    [
        new(@";\s*(DROP|DELETE|UPDATE|INSERT|ALTER|EXEC)\b", RegexOptions.IgnoreCase | RegexOptions.Compiled),
        new(@"'\s*OR\s+'1'\s*=\s*'1", RegexOptions.IgnoreCase | RegexOptions.Compiled),
        new(@"UNION\s+SELECT", RegexOptions.IgnoreCase | RegexOptions.Compiled),
    ];

    public OutputSanitizer(bool sanitizeHtml = true)
    {
        _sanitizeHtml = sanitizeHtml;
        _htmlSanitizer = new HtmlSanitizer();
        // Allow safe formatting tags only
        _htmlSanitizer.AllowedTags.Clear();
        foreach (var tag in new[] { "p", "br", "b", "i", "em", "strong", "ul", "ol", "li", "code", "pre", "h1", "h2", "h3" })
        {
            _htmlSanitizer.AllowedTags.Add(tag);
        }
        _htmlSanitizer.AllowedAttributes.Clear();
    }

    /// <summary>
    /// Sanitizes LLM output text. Returns sanitized text and a list of modifications made.
    /// </summary>
    public (string SanitizedText, List<string> Warnings) Sanitize(string output)
    {
        var warnings = new List<string>();

        if (string.IsNullOrEmpty(output))
            return (output, warnings);

        var sanitized = output;

        // Check for dangerous patterns
        foreach (var pattern in DangerousPatterns)
        {
            if (pattern.IsMatch(sanitized))
            {
                warnings.Add($"Removed dangerous pattern: {pattern}");
                sanitized = pattern.Replace(sanitized, "[REMOVED]");
            }
        }

        // HTML sanitization if enabled
        if (_sanitizeHtml && (sanitized.Contains('<') || sanitized.Contains('>')))
        {
            var before = sanitized;
            sanitized = _htmlSanitizer.Sanitize(sanitized);
            if (before != sanitized)
            {
                warnings.Add("HTML content was sanitized.");
            }
        }

        return (sanitized, warnings);
    }

    /// <summary>
    /// Checks if LLM output contains SQL injection patterns.
    /// Use before passing output to any database query context.
    /// </summary>
    public (bool IsSafe, List<string> Threats) CheckForSqlInjection(string output)
    {
        var threats = new List<string>();
        foreach (var pattern in SqlPatterns)
        {
            if (pattern.IsMatch(output))
            {
                threats.Add($"SQL injection pattern detected: {pattern}");
            }
        }
        return (threats.Count == 0, threats);
    }

    /// <summary>
    /// Validates that LLM output claiming to be JSON is actually valid JSON.
    /// Prevents injection via malformed structured output.
    /// </summary>
    public (bool IsValid, string? Error) ValidateJsonOutput(string output)
    {
        try
        {
            System.Text.Json.JsonDocument.Parse(output);
            return (true, null);
        }
        catch (System.Text.Json.JsonException ex)
        {
            return (false, $"Invalid JSON output: {ex.Message}");
        }
    }
}
