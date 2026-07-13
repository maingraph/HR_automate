#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker Desktop is required." >&2
  exit 1
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from template. Configure it, then run launch.sh again." >&2
  exit 1
fi

echo "Default Sourcer app:     http://localhost:3210"
echo "Default Sourcer API:     http://localhost:8210/docs"
echo "Default Sourcer browser: http://localhost:6210/vnc.html"
echo "Custom .env port overrides are shown by: docker compose ps"
docker compose up --build
