using System.ComponentModel;
using ModelContextProtocol.Server;

namespace AcaMcpServer.Tools;

[McpServerToolType]
public sealed class WeatherTools
{
    [McpServerTool, Description("Get a short weather summary for a city.")]
    public static string GetWeather(
        [Description("City name, e.g. 'Seattle'")] string city)
    {
        // Dummy data — swap for a real API later.
        var samples = new (string City, string Summary)[]
        {
            ("seattle",   "12°C, light rain"),
            ("hyderabad", "31°C, humid and sunny"),
            ("london",    "9°C, overcast"),
            ("dubai",     "36°C, clear")
        };

        var match = samples.FirstOrDefault(s =>
            s.City.Equals(city.Trim(), StringComparison.OrdinalIgnoreCase));

        return match.City is null
            ? $"No forecast for '{city}'. Try Seattle, Hyderabad, London or Dubai."
            : $"Weather in {city}: {match.Summary}.";
    }
}
