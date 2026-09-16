#!/bin/sh
set -eu

mkdir -p /browser-data/profile
# Container replacement can leave Chromium's process-singleton symlinks in
# persistent storage. They are not profile data; remove only these locks so a
# new visible Chromium process can reuse logged-in cookies safely.
rm -f /browser-data/profile/SingletonLock \
  /browser-data/profile/SingletonCookie \
  /browser-data/profile/SingletonSocket
rm -f /tmp/.X99-lock /tmp/.X11-unix/X99
Xvfb :99 -screen 0 1440x900x24 -ac +extension GLX +render -noreset &
xvfb_pid=$!
tries=0
until xdpyinfo -display :99 >/dev/null 2>&1; do
  tries=$((tries + 1))
  [ "$tries" -lt 50 ] || { echo "Xvfb failed to start" >&2; exit 1; }
  sleep 0.1
done
fluxbox >/tmp/fluxbox.log 2>&1 &
fluxbox_pid=$!
x11vnc -display :99 -forever -shared -nopw -rfbport 5900 -listen 0.0.0.0 >/tmp/x11vnc.log 2>&1 &
x11vnc_pid=$!
websockify --web=/usr/share/novnc 6080 localhost:5900 >/tmp/novnc.log 2>&1 &
websockify_pid=$!

cleanup() {
  kill "$xvfb_pid" "$fluxbox_pid" "$x11vnc_pid" "$websockify_pid" 2>/dev/null || true
}
trap 'cleanup; exit 0' TERM INT
uvicorn app.browser_agent.main:app --host 0.0.0.0 --port 8010 &
uvicorn_pid=$!
wait "$uvicorn_pid"
cleanup
