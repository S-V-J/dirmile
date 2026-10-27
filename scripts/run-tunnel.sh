#!/usr/bin/env bash
# ============================================================================
# Dirmile Cloudflare Tunnel Wrapper
#
# Usage: ./scripts/run-tunnel.sh <backend-port>
#
# Modes, chosen from .env (environment overrides):
#   named — TUNNEL_MODE=named + TUNNEL_ID + TUNNEL_CREDS + TUNNEL_HOSTNAME.
#           Runs a pre-created Cloudflare Tunnel on a stable hostname. A
#           per-launch config is generated so the dynamic local port is
#           always the ingress target. The URL is known up front; readiness
#           is proven by the connector registering with the Cloudflare edge
#           (NOT by DNS — a pending zone delegation never resolves).
#   quick — anything missing/unreadable. Ephemeral *.trycloudflare.com
#           hostname, rotates every restart.
#
# Historical bug fixed here: the old version piped cloudflared through tee,
# so $! captured tee's PID. tunnel.pid therefore held the wrong process,
# every stop killed tee and stranded a live cloudflared, and each restart
# leaked one more ghost proxying a dead port. cloudflared now runs with a
# direct redirect ($! is genuinely cloudflared) and an EXIT trap reaps it.
# ============================================================================

set -euo pipefail

BACKEND_PORT="${1:?Usage: run-tunnel.sh <port>}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${PROJECT_ROOT}/logs"
RUNTIME_DIR="${PROJECT_ROOT}/runtime"
LOG_FILE="${LOG_DIR}/tunnel.log"
URL_FILE="${RUNTIME_DIR}/tunnel.url"
CONFIG_FILE="${RUNTIME_DIR}/tunnel-config.yml"
ENV_FILE="${PROJECT_ROOT}/.env"

mkdir -p "${LOG_DIR}" "${RUNTIME_DIR}"
rm -f "${LOG_FILE}" "${URL_FILE}" "${CONFIG_FILE}"

# ── resolve settings: environment wins, then .env ──────────────────────────
env_get() {  # env_get KEY -> prints value, or nothing
  local key="$1"
  if [[ -n "${!key:-}" ]]; then
    printf '%s' "${!key}"
    return 0
  fi
  [[ -f "${ENV_FILE}" ]] || return 0
  sed -n "s/^${key}=//p" "${ENV_FILE}" | tail -n 1 | tr -d '\r'
}

TUNNEL_MODE="$(env_get TUNNEL_MODE)"
TUNNEL_ID="$(env_get TUNNEL_ID)"
TUNNEL_CREDS="$(env_get TUNNEL_CREDS)"
TUNNEL_HOSTNAME="$(env_get TUNNEL_HOSTNAME)"

MODE="quick"
if [[ "${TUNNEL_MODE}" == "named" \
      && -n "${TUNNEL_ID}" && -n "${TUNNEL_CREDS}" && -n "${TUNNEL_HOSTNAME}" ]]; then
  if [[ -f "${TUNNEL_CREDS}" ]]; then
    MODE="named"
  else
    echo "[tunnel] named mode requested but credentials file missing: ${TUNNEL_CREDS}" >&2
    echo "[tunnel] falling back to Quick Tunnel." >&2
  fi
fi

CFD_PID=""
reap() {
  local rc=$?
  if [[ -n "${CFD_PID}" ]] && kill -0 "${CFD_PID}" 2>/dev/null; then
    kill "${CFD_PID}" 2>/dev/null || true
    sleep 1
    kill -9 "${CFD_PID}" 2>/dev/null || true
  fi
  rm -f "${RUNTIME_DIR}/tunnel.pid"
  exit "${rc}"
}
trap reap EXIT INT TERM

echo "[tunnel] mode=${MODE} -> http://127.0.0.1:${BACKEND_PORT}" >&2

if [[ "${MODE}" == "named" ]]; then
  # The local port changes every restart; the hostname does not. Regenerating
  # the ingress config each launch keeps the named tunnel pointed at whatever
  # port Django allocated this time.
  cat > "${CONFIG_FILE}" <<YAML
tunnel: ${TUNNEL_ID}
credentials-file: ${TUNNEL_CREDS}
ingress:
  - hostname: ${TUNNEL_HOSTNAME}
    service: http://localhost:${BACKEND_PORT}
  - service: http_status:404
YAML
  chmod 600 "${CONFIG_FILE}"

  cloudflared tunnel \
    --no-autoupdate \
    --protocol http2 \
    --config "${CONFIG_FILE}" \
    run "${TUNNEL_ID}" \
    > "${LOG_FILE}" 2>&1 &
  CFD_PID=$!
  echo "${CFD_PID}" > "${RUNTIME_DIR}/tunnel.pid"

  # Static hostname: publish it immediately so ./dirmile's poll and
  # runtime/tunnel.url agree without scraping the log.
  echo "https://${TUNNEL_HOSTNAME}" > "${URL_FILE}"
  echo "[tunnel] SUCCESS: https://${TUNNEL_HOSTNAME} (named)" >&2

  # Readiness = connector registration. cloudflared retries internally, so a
  # slow first connect is survivable; a premature exit is not.
  MAX_WAIT=60
  WAITED=0
  REGISTERED=""
  while (( WAITED < MAX_WAIT )); do
    sleep 1
    WAITED=$((WAITED + 1))
    if ! kill -0 "${CFD_PID}" 2>/dev/null; then
      echo "[tunnel] ERROR: cloudflared exited prematurely. Last log lines:" >&2
      tail -n 15 "${LOG_FILE}" >&2 || true
      exit 1
    fi
    if grep -q "Registered tunnel connection" "${LOG_FILE}" 2>/dev/null; then
      REGISTERED="yes"
      break
    fi
    if (( WAITED % 15 == 0 )); then
      echo "[tunnel] waiting for connector registration... (${WAITED}s/${MAX_WAIT}s)" >&2
    fi
  done

  if [[ -z "${REGISTERED}" ]]; then
    echo "[tunnel] WARN: no 'Registered tunnel connection' within ${MAX_WAIT}s." >&2
    echo "[tunnel] cloudflared still running; it retries on its own. Check ${LOG_FILE}." >&2
  fi

  wait "${CFD_PID}"
  exit $?
fi

# ── Quick Tunnel fallback (prior behaviour, PID handling corrected) ────────
cloudflared tunnel \
  --no-autoupdate \
  --protocol http2 \
  --url "http://127.0.0.1:${BACKEND_PORT}" \
  > "${LOG_FILE}" 2>&1 &
CFD_PID=$!
echo "${CFD_PID}" > "${RUNTIME_DIR}/tunnel.pid"

MAX_WAIT=60
WAITED=0
PUBLIC_URL=""
while (( WAITED < MAX_WAIT )); do
  sleep 1
  WAITED=$((WAITED + 1))
  if ! kill -0 "${CFD_PID}" 2>/dev/null; then
    echo "[tunnel] ERROR: cloudflared process exited prematurely." >&2
    tail -n 15 "${LOG_FILE}" >&2 || true
    exit 1
  fi
  PUBLIC_URL=$(grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' "${LOG_FILE}" | head -n 1 || true)
  if [[ -n "${PUBLIC_URL}" ]]; then
    break
  fi
  if (( WAITED % 10 == 0 )); then
    echo "[tunnel] Waiting for URL... (${WAITED}s/${MAX_WAIT}s)" >&2
  fi
done

if [[ -z "${PUBLIC_URL}" ]]; then
  echo "[tunnel] TIMEOUT: Failed to extract URL within ${MAX_WAIT}s." >&2
  exit 1
fi

echo "${PUBLIC_URL}" > "${URL_FILE}"
echo "[tunnel] SUCCESS: ${PUBLIC_URL} (quick)" >&2

wait "${CFD_PID}"
exit $?
