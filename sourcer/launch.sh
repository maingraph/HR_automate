#!/bin/bash
# Sourcer — one-command launcher
# Run from the sourcer/ root: bash launch.sh

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Sourcer launcher"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Redis
if ! command -v redis-server &>/dev/null; then
  echo "▶ Installing Redis via Homebrew…"
  brew install redis
fi
if ! redis-cli ping &>/dev/null 2>&1; then
  echo "▶ Starting Redis…"
  brew services start redis
  sleep 2
fi
echo "✓ Redis running"

# 2. Cleanup stale processes on ports
echo "▶ Cleaning up stale processes on ports 8000 and 3000…"
# Kill processes on port 8000 (API) and 3000 (Frontend)
lsof -ti :8000,3000 | xargs kill -9 2>/dev/null || true
pkill -f "uvicorn" || true
pkill -f "celery" || true
pkill -f "run_telegram_listener.py" || true
pkill -f "next dev" || true
sleep 1

# 3. Frontend npm deps
if [ ! -d "$FRONTEND/node_modules" ]; then
  echo "▶ Installing frontend deps (first time only)…"
  cd "$FRONTEND" && npm install
fi

# 3. Launch all 3 services in background, show combined logs
echo ""
echo "▶ Starting FastAPI backend on :8000"
cd "$BACKEND" && .venv/bin/uvicorn app.main:app --port 8000 --reload &> /tmp/sourcer_api.log &
API_PID=$!

echo "▶ Starting Celery worker"
cd "$BACKEND" && .venv/bin/celery -A app.core.celery_app worker --loglevel=warning &> /tmp/sourcer_celery.log &
CELERY_PID=$!

echo "▶ Starting Celery beat (inbox poller schedule)"
cd "$BACKEND" && .venv/bin/celery -A app.core.celery_app beat --loglevel=warning &> /tmp/sourcer_beat.log &
BEAT_PID=$!

echo "▶ Starting Telegram reply listener"
cd "$BACKEND" && .venv/bin/python ../scripts/run_telegram_listener.py &> /tmp/sourcer_tg_listener.log &
TG_PID=$!

echo "▶ Starting Next.js frontend on :3000"
cd "$FRONTEND" && npm run dev &> /tmp/sourcer_frontend.log &
FE_PID=$!

# Wait for API to be ready
echo "▶ Waiting for API…"
for i in $(seq 1 20); do
  sleep 1
  curl -s --connect-timeout 2 --max-time 2 http://localhost:8000/health &>/dev/null && break
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✓ All services running"
echo "  Frontend  →  http://localhost:3000"
echo "  API       →  http://localhost:8000/docs"
echo ""
echo "  Logs:  tail -f /tmp/sourcer_api.log"
echo "         tail -f /tmp/sourcer_celery.log"
echo "         tail -f /tmp/sourcer_beat.log"
echo "         tail -f /tmp/sourcer_tg_listener.log"
echo "         tail -f /tmp/sourcer_frontend.log"
echo ""
echo "  Stop:  kill $API_PID $CELERY_PID $BEAT_PID $TG_PID $FE_PID"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Keep script alive, kill children on Ctrl+C
trap "kill $API_PID $CELERY_PID $BEAT_PID $TG_PID $FE_PID 2>/dev/null; brew services stop redis; echo 'Stopped.'" EXIT
wait
