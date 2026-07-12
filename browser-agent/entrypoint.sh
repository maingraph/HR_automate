#!/bin/sh
set -eu

mkdir -p /browser-data/profile
Xvfb :99 -screen 0 1440x900x24 -ac +extension GLX +render -noreset &
tries=0
until xdpyinfo -display :99 >/dev/null 2>&1; do
  tries=$((tries + 1))
  [ "$tries" -lt 50 ] || { echo "Xvfb failed to start" >&2; exit 1; }
  sleep 0.1
done
fluxbox >/tmp/fluxbox.log 2>&1 &
x11vnc -display :99 -forever -shared -nopw -rfbport 5900 -listen 0.0.0.0 >/tmp/x11vnc.log 2>&1 &
websockify --web=/usr/share/novnc 6080 localhost:5900 >/tmp/novnc.log 2>&1 &

exec uvicorn app.browser_agent.main:app --host 0.0.0.0 --port 8010
