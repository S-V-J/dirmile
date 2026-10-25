#!/usr/bin/env bash
# ============================================================================
# Dirmile Cloudflare Tunnel Wrapper
# 
# Usage: ./scripts/run-tunnel.sh <backend-port>
#
# Responsibilities:
#   1. Launch cloudflared in foreground (managed by this script's caller).
#   2. Capture stdout/stderr to logs/tunnel.log immediately.
#   3. Extract the public URL as soon as it appears.
#   4. Write URL to runtime/tunnel.url.
#   5. Exit cleanly when killed.
# ============================================================================

set -euo pipefail

BACKEND_PORT="${1:?Usage: run-tunnel.sh <port>}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${PROJECT_ROOT}/logs"
RUNTIME_DIR="${PROJECT_ROOT}/runtime"
LOG_FILE="${LOG_DIR}/tunnel.log"
URL_FILE="${RUNTIME_DIR}/tunnel.url"

mkdir -p "${LOG_DIR}" "${RUNTIME_DIR}"

# Clean slate
rm -f "${LOG_FILE}" "${URL_FILE}"

echo "[tunnel] Starting cloudflared -> http://127.0.0.1:${BACKEND_PORT}" >&2

# Run cloudflared. 
# We use tee to ensure we see output in real-time AND capture it to file.
# --no-autoupdate prevents permission issues in WSL/container environments.
cloudflared tunnel \
  --no-autoupdate \
  --protocol http2 \
  --url "http://127.0.0.1:${BACKEND_PORT}" \
  2>&1 | tee "${LOG_FILE}" &

CFD_PID=$!
echo "${CFD_PID}" > "${RUNTIME_DIR}/tunnel.pid"

# Wait for URL extraction
MAX_WAIT=60
WAITED=0
PUBLIC_URL=""

while (( WAITED < MAX_WAIT )); do
  sleep 1
  WAITED=$((WAITED + 1))

  # Check if process died early
  if ! kill -0 "${CFD_PID}" 2>/dev/null; then
    echo "[tunnel] ERROR: cloudflared process exited prematurely." >&2
    exit 1
  fi

  # Extract URL from log file
  # Pattern: https://<random-subdomain>.trycloudflare.com
  PUBLIC_URL=$(grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' "${LOG_FILE}" | head -n 1 || true)

  if [[ -n "${PUBLIC_URL}" ]]; then
    break
  fi
  
  # Progress feedback every 10s
  if (( WAITED % 10 == 0 )); then
    echo "[tunnel] Waiting for URL... (${WAITED}s/${MAX_WAIT}s)" >&2
  fi
done

if [[ -z "${PUBLIC_URL}" ]]; then
  echo "[tunnel] TIMEOUT: Failed to extract URL within ${MAX_WAIT}s." >&2
  kill "${CFD_PID}" 2>/dev/null || true
  rm -f "${RUNTIME_DIR}/tunnel.pid"
  exit 1
fi

echo "${PUBLIC_URL}" > "${URL_FILE}"
echo "[tunnel] SUCCESS: ${PUBLIC_URL}" >&2

# Keep script alive until cloudflared exits
wait "${CFD_PID}"
EXIT_CODE=$?

# Cleanup on exit
rm -f "${RUNTIME_DIR}/tunnel.pid"
exit ${EXIT_CODE}
