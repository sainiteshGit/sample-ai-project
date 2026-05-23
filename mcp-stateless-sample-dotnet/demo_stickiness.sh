#!/usr/bin/env bash
# Demonstrates the routing problem the 2026-07-28 MCP RC is designed to fix.
#
#   Scenario 1 (today's protocol, MCP 2025-11-25):
#     SDK client -> round-robin LB -> A or B
#     The 2nd request lands on the wrong pod -> "Session not found" error.
#
#   Scenario 2 (2026-07-28-style: no Mcp-Session-Id, explicit handles, shared store):
#     curl -> round-robin LB -> A or B (sharing a JSON file as the "Redis" stand-in)
#     Every request succeeds and both pods serve the same basket.

set -e
cd "$(dirname "$0")"

SHARED_STORE="$(pwd)/.shared-basket-store.json"
rm -f "$SHARED_STORE"

cleanup() {
  echo
  echo "--- Stopping all processes ---"
  kill $A_PID $B_PID $LB_PID 2>/dev/null || true
  wait $A_PID $B_PID $LB_PID 2>/dev/null || true
}
trap cleanup EXIT INT TERM

dotnet build --nologo -v quiet >/dev/null

SHARED_STORE_PATH="$SHARED_STORE" INSTANCE_ID=A PORT=8001 \
  dotnet run --project Server/Server.csproj --no-build -c Debug >/tmp/srv-A.log 2>&1 &
A_PID=$!
SHARED_STORE_PATH="$SHARED_STORE" INSTANCE_ID=B PORT=8002 \
  dotnet run --project Server/Server.csproj --no-build -c Debug >/tmp/srv-B.log 2>&1 &
B_PID=$!
PORT=8000 dotnet run --project LoadBalancer/LoadBalancer.csproj --no-build -c Debug >/tmp/lb.log 2>&1 &
LB_PID=$!

# Wait for the LB to accept connections.
for i in {1..30}; do
  if curl -sf http://127.0.0.1:8000/whoami >/dev/null 2>&1; then break; fi
  sleep 0.5
done

echo
echo "========================================================================"
echo " SCENARIO 1 — MCP 2025-11-25 (SDK 1.3.0) through a round-robin LB"
echo " Expected: client fails because the 2nd request lands on the wrong pod."
echo "========================================================================"
set +e
dotnet run --project Client/Client.csproj --no-build -c Debug http://127.0.0.1:8000 2>&1 | tail -25
RC=$?
set -e
echo
echo "[scenario 1 exit code: $RC]"
echo
echo "--- LB routing log (scenario 1) ---"
tail -n 20 /tmp/lb.log

echo
echo "========================================================================"
echo " SCENARIO 2 — 2026-07-28-style stateless POSTs through the SAME LB"
echo " Expected: every request succeeds; both pods serve the same basket."
echo "========================================================================"

create_payload='{"name":"create_basket","arguments":{"owner":"alice"}}'
echo
echo "POST /stateless/tools/call  (create_basket)"
CREATE_RES=$(curl -sf -X POST -H 'Content-Type: application/json' \
  -d "$create_payload" http://127.0.0.1:8000/stateless/tools/call)
echo "  -> $CREATE_RES"
BASKET_ID=$(echo "$CREATE_RES" | python3 -c "import sys,json;print(json.load(sys.stdin)['basket_id'])")

for sku in book-001 mug-042 pen-007; do
  echo
  echo "POST /stateless/tools/call  (add_item sku=$sku)"
  curl -sf -X POST -H 'Content-Type: application/json' \
    -d "{\"name\":\"add_item\",\"arguments\":{\"basket_id\":\"$BASKET_ID\",\"sku\":\"$sku\"}}" \
    http://127.0.0.1:8000/stateless/tools/call
  echo
done

echo
echo "POST /stateless/tools/call  (view_basket)"
curl -sf -X POST -H 'Content-Type: application/json' \
  -d "{\"name\":\"view_basket\",\"arguments\":{\"basket_id\":\"$BASKET_ID\"}}" \
  http://127.0.0.1:8000/stateless/tools/call
echo

echo
echo "--- LB routing log (scenario 2) ---"
tail -n 12 /tmp/lb.log

echo
echo "Notice in the LB log above: requests alternate between pod A and pod B,"
echo "yet the basket is consistent because the shared store (file) is keyed by"
echo "the explicit handle the tool minted, not by a transport session id."
