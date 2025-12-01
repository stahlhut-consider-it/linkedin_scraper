#!/usr/bin/env bash
set -euo pipefail

# Run Chrome in a virtual display so the scraper can stay headful inside the container.
export DISPLAY="${DISPLAY:-:99}"
XVFB_RESOLUTION="${XVFB_RESOLUTION:-1920x1080x24}"

cleanup() {
  if [[ -n "${XVFB_PID:-}" ]]; then
    kill "${XVFB_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

Xvfb "${DISPLAY}" -screen 0 "${XVFB_RESOLUTION}" -nolisten tcp -ac &
XVFB_PID=$!

# Give Xvfb a moment to start so Chrome can connect.
sleep 2

exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers
