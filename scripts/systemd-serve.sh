#!/usr/bin/env bash
# ============================================================================
# Dirmile systemd foreground launcher.
#
# Allocates a DYNAMIC free port on every start (no fixed port anywhere in the
# project), records it to runtime/systemd.port for discovery, then exec()s
# Django in the FOREGROUND so systemd's MainPID is the real server and
# stop/restart signal it directly. Type=simple in the unit is therefore correct.
#
# Writes a DISTINCT filename (systemd.port, not dirmile.port) so an enabled
# service never clobbers or races the ./dirmile CLI's own state files.
# ============================================================================
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${PROJECT_ROOT}/runtime"
PYTHON="${PROJECT_ROOT}/venv/bin/python"

mkdir -p "${RUNTIME_DIR}"
[[ -x "${PYTHON}" ]] || { echo "[dirmile-systemd] venv python missing: ${PYTHON}" >&2; exit 1; }

# Same allocator the CLI uses: bind port 0, read the assigned port, close.
PORT="$("${PYTHON}" - <<'PY'
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(("0.0.0.0", 0))
print(s.getsockname()[1])
s.close()
PY
)"

printf '%s\n' "${PORT}" > "${RUNTIME_DIR}/systemd.port"
echo "[dirmile-systemd] dynamic port ${PORT} (no fixed port)" >&2

cd "${PROJECT_ROOT}/Backend"
exec "${PYTHON}" manage.py runserver "0.0.0.0:${PORT}" --noreload
