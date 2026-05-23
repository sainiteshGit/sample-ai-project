#!/usr/bin/env bash
# Start two instances of the stateless MCP sample server on 8001 and 8002.
# They share no state - the demo client picks one at random per request.

set -e
cd "$(dirname "$0")"

cleanup() {
  echo
  echo "Stopping server instances..."
  kill "$A_PID" "$B_PID" 2>/dev/null || true
  wait "$A_PID" "$B_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Build once so both background runs reuse the artifacts.
dotnet build Server/Server.csproj -c Debug --nologo -v quiet

INSTANCE_ID=A PORT=8001 dotnet run --project Server/Server.csproj --no-build -c Debug &
A_PID=$!
INSTANCE_ID=B PORT=8002 dotnet run --project Server/Server.csproj --no-build -c Debug &
B_PID=$!

echo "Instance A (pid $A_PID) on :8001"
echo "Instance B (pid $B_PID) on :8002"
echo "Press Ctrl+C to stop. In a separate terminal: dotnet run --project Client/Client.csproj"
wait
