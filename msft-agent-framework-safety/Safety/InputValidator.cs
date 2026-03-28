using System.Text.RegularExpressions;
using Microsoft.Extensions.AI;

namespace AgentSafetySample.Safety;

/// <summary>
/// Validates and sanitizes user input before it reaches the agent.
/// Implements: allow-listing, length limits, blocked patterns, path traversal prevention.
/// </summary>
public sealed class InputValidator
{
    private readonly int _maxInputLength;
    private readonly Regex[] _blockedPatterns;
    private readonly string[] _allowedDirectories;

    public InputValidator(int maxInputLength, string[] blockedPatterns, string[] allowedDirectories)
    {
        _maxInputLength = maxInputLength;
        _blockedPatterns = blockedPatterns
            .Select(p => new Regex(p, RegexOptions.IgnoreCase | RegexOptions.Compiled))
            .ToArray();
        _allowedDirectories = allowedDirectories
            .Select(d => Path.GetFullPath(d))
            .ToArray();
    }

    /// <summary>
    /// Validates user input. Returns a list of violations (empty = valid).
    /// </summary>
    public List<string> Validate(string input)
    {
        var violations = new List<string>();

        if (string.IsNullOrWhiteSpace(input))
        {
            violations.Add("Input is empty or whitespace.");
            return violations;
        }

        // Length limit
        if (input.Length > _maxInputLength)
        {
            violations.Add($"Input exceeds maximum length of {_maxInputLength} characters (got {input.Length}).");
        }

        // Blocked patterns (XSS, script injection)
        foreach (var pattern in _blockedPatterns)
        {
            if (pattern.IsMatch(input))
            {
                violations.Add($"Input contains blocked pattern: {pattern}");
            }
        }

        return violations;
    }

    /// <summary>
    /// Validates that a file path is within allowed directories (allow-listing).
    /// Prevents path traversal attacks.
    /// </summary>
    public (bool IsValid, string? ResolvedPath, string? Error) ValidateFilePath(string filePath)
    {
        try
        {
            var resolvedPath = Path.GetFullPath(filePath);

            foreach (var allowedDir in _allowedDirectories)
            {
                if (resolvedPath.StartsWith(allowedDir, StringComparison.OrdinalIgnoreCase))
                {
                    return (true, resolvedPath, null);
                }
            }

            return (false, null, $"Path '{filePath}' is outside allowed directories.");
        }
        catch (Exception ex)
        {
            return (false, null, $"Invalid path: {ex.Message}");
        }
    }

    /// <summary>
    /// Validates function tool arguments — type checks, range constraints, string lengths.
    /// </summary>
    public List<string> ValidateFunctionArgs(string functionName, IDictionary<string, object?> args)
    {
        var violations = new List<string>();

        foreach (var (key, value) in args)
        {
            // String length limits
            if (value is string s && s.Length > 10_000)
            {
                violations.Add($"{functionName}.{key}: String argument exceeds 10,000 character limit.");
            }

            // Null check for required args
            if (value is null)
            {
                // Allow nulls — they're optional. The function itself should handle missing args.
                continue;
            }

            // Path traversal check for path-like arguments
            if (key.Contains("path", StringComparison.OrdinalIgnoreCase) ||
                key.Contains("file", StringComparison.OrdinalIgnoreCase) ||
                key.Contains("dir", StringComparison.OrdinalIgnoreCase))
            {
                if (value is string pathValue)
                {
                    var (isValid, _, error) = ValidateFilePath(pathValue);
                    if (!isValid)
                    {
                        violations.Add($"{functionName}.{key}: {error}");
                    }
                }
            }

            // SQL injection patterns in string args
            if (value is string strValue)
            {
                foreach (var pattern in _blockedPatterns)
                {
                    if (pattern.IsMatch(strValue))
                    {
                        violations.Add($"{functionName}.{key}: Argument contains blocked pattern.");
                    }
                }
            }
        }

        return violations;
    }
}
