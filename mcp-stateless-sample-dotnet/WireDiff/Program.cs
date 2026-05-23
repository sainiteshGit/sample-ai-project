// WireDiff — appendix to the SDK sample.
//
// Prints the *raw HTTP wire shape* that the same `add_item` tool call takes
// under two MCP revisions:
//
//   * 2025-11-25 (the protocol shipped by ModelContextProtocol 1.3.0 today)
//   * 2026-07-28 (the release candidate, locked May 21, 2026)
//
// Source SEPs for the RC shape:
//   * SEP-2567 — remove Mcp-Session-Id and the protocol-level session
//   * SEP-2575 — remove initialize/initialized; clientInfo to _meta; server/discover
//   * SEP-2243 — require Mcp-Method / Mcp-Name headers on Streamable HTTP
//   * SEP-2322 — Multi Round-Trip Requests / InputRequiredResult + requestState
//   * SEP-2549 — ttlMs + cacheScope on list / resource results
//   * SEP-2164 — missing-resource error code -32002 -> -32602
//
// This program makes no network calls. It is a printable comparison only.

using System;

PrintHeader("MCP 2025-11-25  (what ModelContextProtocol 1.3.0 sends today)");

Print("""
  >> Step 1: initialize handshake (one extra round-trip per session)

     POST /mcp HTTP/1.1
     Host: server.example.com
     Content-Type: application/json
     Accept: application/json, text/event-stream

     {
       "jsonrpc": "2.0",
       "id": 1,
       "method": "initialize",
       "params": {
         "protocolVersion": "2025-11-25",
         "capabilities": { "roots": { "listChanged": true } },
         "clientInfo": { "name": "stateless-sample-client", "version": "1.0.0" }
       }
     }

  << HTTP/1.1 200 OK
     Mcp-Session-Id: 0e6f...c1            <-- server-minted session handle
     Content-Type: application/json

     { "jsonrpc": "2.0", "id": 1, "result": { ... } }

  >> Step 2: tools/call — every subsequent request must carry Mcp-Session-Id

     POST /mcp HTTP/1.1
     Mcp-Session-Id: 0e6f...c1            <-- routing pins this to one server
     Content-Type: application/json

     {
       "jsonrpc": "2.0", "id": 2,
       "method": "tools/call",
       "params": {
         "name": "add_item",
         "arguments": { "basket_id": "bskt_54c439b", "sku": "book-001" }
       }
     }

  Implication: a load balancer cannot freely route — the session id is sticky.
""");

PrintHeader("MCP 2026-07-28  (release candidate — stateless by design)");

Print("""
  >> No initialize handshake. First call is the tool call.

     POST /mcp HTTP/1.1
     Host: server.example.com
     Content-Type: application/json
     Accept: application/json, text/event-stream
     Mcp-Method: tools/call                <-- SEP-2243: method in a header
     Mcp-Name:   add_item                  <-- SEP-2243: name   in a header
     Mcp-Protocol-Version: 2026-07-28

     {
       "jsonrpc": "2.0", "id": 1,
       "method": "tools/call",
       "params": {
         "name": "add_item",
         "arguments": { "basket_id": "bskt_54c439b", "sku": "book-001" },
         "_meta": {
           "io.modelcontextprotocol/clientInfo": {        // SEP-2575
             "name": "stateless-sample-client",
             "version": "1.0.0",
             "protocolVersion": "2026-07-28"
           }
         }
       }
     }

  << HTTP/1.1 200 OK                       <-- no Mcp-Session-Id, ever
     Content-Type: application/json

     {
       "jsonrpc": "2.0", "id": 1,
       "result": {
         "structuredContent": { "basket_id": "bskt_54c439b", "items": [...] },
         "_meta": {
           "io.modelcontextprotocol/cache": {            // SEP-2549
             "ttlMs": 0,
             "cacheScope": "session"
           }
         }
       }
     }

  Mid-call user input (replaces SSE-based elicitation):

     { "jsonrpc": "2.0", "id": 1,
       "result": {
         "type": "inputRequired",                        // SEP-2322
         "requestState": "opaque-server-token",
         "prompt": { "schema": { ... }, "message": "Confirm quantity?" }
       } }

   ...client gathers input, resumes by POSTing the same tool/call with
      _meta.io.modelcontextprotocol/inputResponse + requestState.

  Implication: every request stands on its own. Any replica can serve it,
  because all state lives behind the *handle the tool minted* (basket_id),
  not behind a transport session id.
""");

PrintHeader("Diff at a glance");

Print("""
                              2025-11-25 (today)        2026-07-28 (RC)
   ----------------------------------------------------------------------
   initialize handshake       required, 1 RTT           removed (SEP-2575)
   Mcp-Session-Id header      required after init       gone     (SEP-2567)
   Method discovery           JSON-RPC body only        Mcp-Method header (SEP-2243)
   Client identity per call   only at initialize        _meta.clientInfo  (SEP-2575)
   Mid-call user input        SSE-stream elicitation    InputRequiredResult (SEP-2322)
   Cache hints                none                      _meta.cache       (SEP-2549)
   Server discovery           initialize result         server/discover   (SEP-2575)
   Load-balancer affinity     sticky by Session-Id      stateless         (-)
""");

static void PrintHeader(string title)
{
    Console.WriteLine();
    Console.WriteLine(new string('=', 72));
    Console.WriteLine($"  {title}");
    Console.WriteLine(new string('=', 72));
}

static void Print(string body) => Console.WriteLine(body);
