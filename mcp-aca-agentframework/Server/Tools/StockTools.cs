using System.ComponentModel;
using ModelContextProtocol.Server;

namespace AcaMcpServer.Tools;

[McpServerToolType]
public sealed class StockTools
{
    [McpServerTool, Description("Get a fake last-traded price for a ticker symbol.")]
    public static string GetStockPrice(
        [Description("Ticker symbol, e.g. 'MSFT'")] string symbol)
    {
        var prices = new Dictionary<string, decimal>(StringComparer.OrdinalIgnoreCase)
        {
            ["MSFT"]  = 512.40m,
            ["AAPL"]  = 233.10m,
            ["GOOGL"] = 198.75m,
            ["NVDA"]  = 141.20m
        };

        return prices.TryGetValue(symbol.Trim(), out var price)
            ? $"{symbol.ToUpperInvariant()} last traded at ${price:0.00} (mock)."
            : $"No price for '{symbol}'. Try MSFT, AAPL, GOOGL, NVDA.";
    }
}
