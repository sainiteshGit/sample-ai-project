# MCP Stateless Sample (.NET)

A teaching sample built around the **MCP [2026-07-28 release candidate](https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/)**, which makes the protocol *stateless by design* at the transport layer.

Two parts:

1. **Working sample** — a server + client built on the official [`ModelContextProtocol`](https://www.nuget.org/packages/ModelContextProtocol) C# SDK (v1.3.0), following [Get started with MCP in .NET](https://learn.microsoft.com/dotnet/ai/get-started-mcp). The tools use the **explicit-handle pattern** (`basket_id` minted by the server and threaded back by the model) — the same pattern that becomes mandatory in 2026-07-28.
2. **Wire-diff appendix** — a printable console (`WireDiff`) that shows the *raw HTTP shape* of the same `add_item` call under 2025-11-25 vs 2026-07-28, side by side, with SEP references.

> **Why the split?** The C# SDK today targets MCP **`2025-11-25`** only (latest version is 1.3.0). The 2026-07-28 wire format was locked May 21, 2026; SDK support is expected during the ten-week validation window before the July 28, 2026 final release. Until then, the wire diff is the most honest way to show what's changing.

## What you'll see

* The SDK sample runs end-to-end. The model calls `create_basket`, then `add_item` three times, then `view_basket` — all using `basket_id` as the handle, with no transport session involved at the application layer.
* `run_servers.sh` starts two independent server instances (`A` on :8001 and `B` on :8002) that share no state. The client connects to one for the demo. In a load-balanced deployment, the explicit-handle pattern means any replica can serve any request — which is exactly what 2026-07-28 enforces protocol-wide.
* `WireDiff` prints both wire formats side-by-side so you can see what changes underneath the SDK once it adopts 2026-07-28.

## Layout

```
mcp-stateless-sample-dotnet/
├── McpStatelessSample.sln
├── Server/                 # ASP.NET Core MCP server (SDK 1.3.0)
│   ├── Program.cs
│   ├── Server.csproj
│   └── Tools/BasketTools.cs
├── Client/                 # Console MCP client (SDK 1.3.0)
│   ├── Program.cs
│   └── Client.csproj
├── WireDiff/               # Printable 2025-11-25 vs 2026-07-28 comparison
│   ├── Program.cs
│   └── WireDiff.csproj
└── run_servers.sh          # Starts two server instances on :8001 and :8002
```

## Run it

Requires **.NET 10 SDK**.

```bash
cd mcp-stateless-sample-dotnet

# Build once
dotnet build

# Terminal 1 — start both server instances
./run_servers.sh

# Terminal 2 — run the SDK demo client (defaults to http://127.0.0.1:8001)
dotnet run --project Client/Client.csproj

# Any terminal — print the wire-format diff
dotnet run --project WireDiff/WireDiff.csproj
```

Sample client output:

```
1. List tools
  - create_basket: Create a new shopping basket and return its handle (basket_id).
  - view_basket:   Return the contents of a basket.
  - add_item:      Add an item to a basket by basket_id.

2. Explicit-handle pattern — create_basket -> add_item -> view_basket
  basket bskt_54c439b created on A
  added book-001 via A
  added mug-042 via A
  added pen-007 via A
  final view: 3 items, served by A
```

## The headline changes (from the RC blog)

| Change | SEP | Where you see it |
|---|---|---|
| Remove `Mcp-Session-Id` and the protocol-level session | [SEP-2567](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2567) | `WireDiff` |
| Remove `initialize` handshake; `clientInfo` moves to `_meta`; `server/discover` added | [SEP-2575](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2575) | `WireDiff` |
| Require `Mcp-Method` / `Mcp-Name` headers on Streamable HTTP | [SEP-2243](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2243) | `WireDiff` |
| `InputRequiredResult` + `requestState` replaces SSE-based elicitation | [SEP-2322](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2322) | `WireDiff` |
| `ttlMs` + `cacheScope` on list / resource results | [SEP-2549](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2549) | `WireDiff` |
| Missing-resource error code `-32002` → `-32602` | [SEP-2164](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2164) | `WireDiff` |
| Explicit-handle pattern for stateful business logic | — | `BasketTools.cs` |

## What this is not

* **Not a 2026-07-28 implementation.** The SDK doesn't ship that yet. The Server/Client sample speaks 2025-11-25 under the hood — `WireDiff` is where you see the new format.
* **Not production code.** No auth, no retries, no rate limiting, no persistence — `BasketStore` is an in-memory `ConcurrentDictionary`.
* **Not a complete MCP server.** Only the `tools/*` surface is exercised; no `resources/*` or `prompts/*`.

The goal is to make the protocol shift concrete enough to reason about, while writing idiomatic SDK code you can keep using once 2026-07-28 lands.
