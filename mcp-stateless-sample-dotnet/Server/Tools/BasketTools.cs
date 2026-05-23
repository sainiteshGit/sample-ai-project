using System.Collections.Concurrent;
using System.ComponentModel;
using System.Text.Json;
using ModelContextProtocol.Server;

namespace McpStatelessSample.Server.Tools;

/// <summary>
/// Store keyed by an explicit, model-visible handle (basket_id). When the
/// SHARED_STORE_PATH env var is set, all instances share a single JSON file
/// on disk — this simulates Redis/Cosmos in a horizontally-scaled deployment.
/// Otherwise the store is per-process (in-memory).
///
/// The explicit-handle pattern is what the 2026-07-28 release candidate makes
/// mandatory: state must be reachable from any server instance via an
/// argument the model passes in, NOT via the transport session id.
/// </summary>
public sealed class BasketStore
{
    private readonly ConcurrentDictionary<string, Basket> _memory = new();
    private readonly string? _sharedPath = Environment.GetEnvironmentVariable("SHARED_STORE_PATH");
    private readonly object _fileLock = new();

    public bool IsShared => _sharedPath is not null;

    public string Create(string owner)
    {
        var id = $"bskt_{Guid.NewGuid():N}"[..12];
        var basket = new Basket(owner, new List<BasketItem>());
        Write(id, basket);
        return id;
    }

    public Basket Get(string id) =>
        ReadAll().TryGetValue(id, out var b)
            ? b
            : throw new KeyNotFoundException($"Unknown basket_id: {id}");

    public void AddItem(string id, string sku, int qty)
    {
        lock (_fileLock)
        {
            var all = ReadAll();
            if (!all.TryGetValue(id, out var basket))
                throw new KeyNotFoundException($"Unknown basket_id: {id}");
            basket.Items.Add(new BasketItem(sku, qty));
            Write(id, basket);
        }
    }

    private Dictionary<string, Basket> ReadAll()
    {
        if (_sharedPath is null)
            return new(_memory);

        lock (_fileLock)
        {
            if (!File.Exists(_sharedPath)) return new();
            var json = File.ReadAllText(_sharedPath);
            if (string.IsNullOrWhiteSpace(json)) return new();
            return JsonSerializer.Deserialize<Dictionary<string, Basket>>(json) ?? new();
        }
    }

    private void Write(string id, Basket basket)
    {
        if (_sharedPath is null)
        {
            _memory[id] = basket;
            return;
        }
        lock (_fileLock)
        {
            var all = ReadAll();
            all[id] = basket;
            File.WriteAllText(_sharedPath, JsonSerializer.Serialize(all));
        }
    }
}

public record Basket(string Owner, List<BasketItem> Items);
public record BasketItem(string Sku, int Qty);

[McpServerToolType]
public sealed class BasketTools
{
    private readonly BasketStore _store;
    private readonly string _instance;

    public BasketTools(BasketStore store)
    {
        _store = store;
        _instance = Environment.GetEnvironmentVariable("INSTANCE_ID") ?? "srv-?";
    }

    [McpServerTool, Description("Create a new shopping basket and return its handle (basket_id).")]
    public object CreateBasket(
        [Description("Owner display name for the basket.")] string owner = "anonymous")
    {
        var id = _store.Create(owner);
        return new { basket_id = id, created_by_instance = _instance };
    }

    [McpServerTool, Description("Add an item to a basket by basket_id.")]
    public object AddItem(
        [Description("The basket handle returned by create_basket.")] string basket_id,
        [Description("Stock-keeping unit identifier.")] string sku,
        [Description("Quantity to add. Defaults to 1.")] int qty = 1)
    {
        _store.AddItem(basket_id, sku, qty);
        var basket = _store.Get(basket_id);
        return new
        {
            basket_id,
            items = basket.Items,
            handled_by_instance = _instance,
        };
    }

    [McpServerTool, Description("Return the contents of a basket.")]
    public object ViewBasket(
        [Description("The basket handle returned by create_basket.")] string basket_id)
    {
        var basket = _store.Get(basket_id);
        return new
        {
            basket_id,
            basket.Owner,
            basket.Items,
            handled_by_instance = _instance,
        };
    }
}
