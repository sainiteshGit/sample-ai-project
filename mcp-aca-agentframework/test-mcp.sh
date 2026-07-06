#!/usr/bin/env bash
# Quick raw-JSON-RPC test of the deployed MCP server. No agent, no LLM.
# Usage: ./test-mcp.sh [server-url]

set -e
URL="${1:-https://ca-mcp-server-npmgs2d4h6f6u.nicemushroom-9745b9be.eastus.azurecontainerapps.io/mcp}"

extract_json() {
  # Handles both plain JSON and text/event-stream ("data: {...}") replies.
  awk '/^data:/{sub(/^data: /,""); print; exit} /^{/{print; exit}'
}

echo "MCP server: $URL"
echo

echo "===== 1) initialize ====="
curl -s -D /tmp/mcp_headers.txt -X POST "$URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"curl-test","version":"1.0"}}}' \
  | extract_json | head -c 500
echo
SESSION_ID=$(grep -i '^mcp-session-id' /tmp/mcp_headers.txt | awk '{print $2}' | tr -d '\r\n')
echo "session-id: $SESSION_ID"
echo

echo "===== 2) notifications/initialized ====="
curl -s -o /dev/null -w "http=%{http_code}\n" -X POST "$URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'
echo

echo "===== 3) tools/list ====="
curl -s -X POST "$URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  | extract_json | head -c 800
echo
echo

echo "===== 4) tools/call get_weather(city=Hyderabad) ====="
curl -s -X POST "$URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"get_weather","arguments":{"city":"Hyderabad"}}}' \
  | extract_json | head -c 500
echo
echo

echo "===== 5) tools/call get_stock_price(symbol=NVDA) ====="
curl -s -X POST "$URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"get_stock_price","arguments":{"symbol":"NVDA"}}}' \
  | extract_json | head -c 500
echo
