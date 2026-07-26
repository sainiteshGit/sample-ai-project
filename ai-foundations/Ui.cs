using System.Text.Json;

namespace Lab01;

/// <summary>Console formatting only. Nothing interesting here.</summary>
internal static class Ui
{
    private const int Width = 76;

    private static readonly JsonSerializerOptions Pretty = new() { WriteIndented = true };

    public static void Rule(char c = '-') => Console.WriteLine("  " + new string(c, Width));

    public static void Header(int n, string title)
    {
        Console.WriteLine();
        Rule('=');
        Console.WriteLine($"  EXPERIMENT {n}: {title}");
        Rule('=');
    }

    public static void Banner(string line1, params string[] rest)
    {
        Console.WriteLine();
        Rule('#');
        Console.WriteLine("  " + line1);
        foreach (var r in rest) Console.WriteLine("  " + r);
        Rule('#');
    }

    /// <summary>The commentary blocks. This is the actual content of the lab.</summary>
    public static void Note(string text)
    {
        Console.WriteLine();
        foreach (var line in text.Replace("\r", "").Split('\n'))
            Console.WriteLine("  | " + line);
        Console.WriteLine();
    }

    public static void Json(object o) =>
        Console.WriteLine("    " + JsonSerializer.Serialize(o, Pretty).Replace("\n", "\n    "));
}
