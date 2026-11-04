#!/bin/bash
# Mood Receipt kiosk: start | stop | toggle (default: start)
set -u
ROOT="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
RUN_DIR="${XDG_RUNTIME_DIR:-/tmp}/mood_receipt"
PROFILE="${XDG_DATA_HOME:-$HOME/.local/share}/mood_receipt/chromium"
PORT=8765
mkdir -p "$RUN_DIR" "$PROFILE"

stop_kiosk() {
  [ -f "$RUN_DIR/pid" ] && kill "$(cat "$RUN_DIR/pid")" 2>/dev/null
}

case "${1:-start}" in
  stop) stop_kiosk; exit 0 ;;
  toggle) stop_kiosk && exit 0 ;;
  start) ;;
  *) echo "usage: $0 [start|stop|toggle]" >&2; exit 2 ;;
esac

# Only one kiosk at a time, so a double-tapped launcher does nothing.
exec 9>"$RUN_DIR/lock"
flock -n 9 || { echo "Mood Receipt kiosk is already running." >&2; exit 0; }
echo $$ > "$RUN_DIR/pid"

SERVER=""; BROWSER=""
cleanup() {
  trap - EXIT
  [ -n "$BROWSER" ] && kill "$BROWSER" 2>/dev/null
  [ -n "$SERVER" ] && kill "$SERVER" 2>/dev/null
  rm -f "$RUN_DIR/pid"
}
trap cleanup EXIT
trap 'exit 0' TERM INT

MOOD_KIOSK_PID=$$ python3 "$ROOT/server.py" --port "$PORT" >"$RUN_DIR/server.log" 2>&1 9>&- &
SERVER=$!
for _ in $(seq 50); do
  curl -fs "http://127.0.0.1:$PORT/health" >/dev/null && break
  sleep 0.1
done
curl -fs "http://127.0.0.1:$PORT/health" >/dev/null || { echo "Server didn't start; see $RUN_DIR/server.log" >&2; exit 1; }

# --class becomes the Wayland app id, which labwc's window rule uses to put this on the touch screen.
chromium \
  --kiosk "http://127.0.0.1:$PORT/?kiosk" \
  --class=mood-receipt \
  --user-data-dir="$PROFILE" \
  --ozone-platform=wayland \
  --force-device-scale-factor=1 \
  --password-store=basic \
  --no-first-run \
  --no-default-browser-check \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-pinch \
  --overscroll-history-navigation=0 \
  --disable-features=Translate \
  >"$RUN_DIR/chromium.log" 2>&1 9>&- &
BROWSER=$!
wait "$BROWSER"
