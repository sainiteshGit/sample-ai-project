using System.ComponentModel;

namespace AgentSafetySample.Tools;

/// <summary>
/// Sample function tools that demonstrate safety boundaries.
/// Some are safe (read-only), some are high-risk (side effects).
/// </summary>
public static class SampleTools
{
    // ── Safe tools (no approval required) ──

    [Description("Look up a customer record by ID. Returns name and email.")]
    public static string LookupCustomer(
        [Description("The customer ID (numeric, 1-99999)")] int customerId)
    {
        // Validate range
        if (customerId < 1 || customerId > 99999)
            return "Error: Customer ID must be between 1 and 99999.";

        // Simulated lookup
        return customerId switch
        {
            1001 => "{ \"id\": 1001, \"name\": \"Alice Johnson\", \"email\": \"alice@example.com\", \"tier\": \"gold\" }",
            1002 => "{ \"id\": 1002, \"name\": \"Bob Smith\", \"email\": \"bob@example.com\", \"tier\": \"silver\" }",
            _ => $"{{ \"id\": {customerId}, \"name\": \"Test User\", \"email\": \"test{customerId}@example.com\", \"tier\": \"standard\" }}"
        };
    }

    [Description("Get the current weather for a location.")]
    public static string GetWeather(
        [Description("The city name")] string location)
    {
        if (string.IsNullOrWhiteSpace(location) || location.Length > 200)
            return "Error: Invalid location.";

        return $"{{ \"location\": \"{location}\", \"temp\": \"18°C\", \"condition\": \"Partly cloudy\", \"humidity\": \"65%\" }}";
    }

    [Description("Read a file from the allowed data directory.")]
    public static string ReadFile(
        [Description("The file path (must be within allowed directories)")] string filePath)
    {
        // The InputValidator handles path traversal checks before this is called.
        // This is defense-in-depth: validate again here.
        var resolved = Path.GetFullPath(filePath);
        var allowedBase = Path.GetFullPath("./data");

        if (!resolved.StartsWith(allowedBase, StringComparison.OrdinalIgnoreCase))
            return "Error: Access denied. File is outside allowed directory.";

        if (!File.Exists(resolved))
            return $"Error: File not found: {filePath}";

        return File.ReadAllText(resolved);
    }

    // ── High-risk tools (require approval) ──

    [Description("Delete a customer record permanently. This action is irreversible.")]
    public static string DeleteRecord(
        [Description("The customer ID to delete")] int customerId)
    {
        if (customerId < 1 || customerId > 99999)
            return "Error: Invalid customer ID.";

        // Simulated deletion
        return $"{{ \"deleted\": true, \"customerId\": {customerId}, \"timestamp\": \"{DateTimeOffset.UtcNow:O}\" }}";
    }

    [Description("Send an email to a customer. Irreversible once sent.")]
    public static string SendEmail(
        [Description("The recipient email address")] string toEmail,
        [Description("The email subject line")] string subject,
        [Description("The email body text")] string body)
    {
        if (string.IsNullOrWhiteSpace(toEmail) || !toEmail.Contains('@'))
            return "Error: Invalid email address.";

        if (string.IsNullOrWhiteSpace(subject) || subject.Length > 200)
            return "Error: Subject must be 1-200 characters.";

        if (string.IsNullOrWhiteSpace(body) || body.Length > 5000)
            return "Error: Body must be 1-5000 characters.";

        // Simulated send
        return $"{{ \"sent\": true, \"to\": \"{toEmail}\", \"subject\": \"{subject}\", \"timestamp\": \"{DateTimeOffset.UtcNow:O}\" }}";
    }

    [Description("Execute a shell command on the server. Extremely high risk.")]
    public static string ExecuteCommand(
        [Description("The command to execute")] string command)
    {
        // This should ALWAYS require approval and should be heavily restricted.
        // In this sample we just simulate it.
        if (string.IsNullOrWhiteSpace(command))
            return "Error: Empty command.";

        return $"{{ \"simulated\": true, \"command\": \"[BLOCKED]\", \"note\": \"Command execution is disabled in this sample.\" }}";
    }
}
