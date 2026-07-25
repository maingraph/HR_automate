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

ensure_secret() {
  key="$1"
  placeholder="$2"
  current="$(awk -F= -v key="$key" '$1 == key { sub(/^[^=]*=/, ""); print }' .env | tail -1)"
  if [ -z "$current" ] || [ "$current" = "$placeholder" ]; then
    value="$(openssl rand -base64 24 | tr -d '\n' | tr '/+' '_-')"
    if grep -q "^${key}=" .env; then
      sed -i.bak "s|^${key}=.*|${key}=${value}|" .env
      rm -f .env.bak
    else
      printf '\n%s=%s\n' "$key" "$value" >>.env
    fi
    echo "Generated private ${key} in .env"
  fi
}

ensure_secret BROWSER_VIEWER_TOKEN replace_with_a_private_viewer_token

if [ "${SOURCER_CONFIG_ONLY:-0}" = "1" ]; then
  exit 0
fi

if [ "${SOURCER_WEB_MODE:-0}" = "1" ]; then
  echo "Sourcer web gateway:     http://localhost:${SOURCER_WEB_PORT:-8088}"
else
  echo "Default Sourcer app:     http://localhost:3210"
  echo "Default Sourcer API:     http://localhost:8210/docs"
fi
echo "Embedded browser:        available inside the Sourcer job page"
echo "Custom .env port overrides are shown by: docker compose ps"

DATABASE_MODE="${SOURCER_DATABASE_MODE:-$(awk -F= '$1 == "SOURCER_DATABASE_MODE" { print $2 }' .env | tail -1)}"
compose_files=(-f docker-compose.yml)
if [ "${DATABASE_MODE:-local}" = "external" ]; then
  echo "Database: external Supabase"
else
  echo "Database: private local PostgreSQL"
  compose_files+=(-f docker-compose.local.yml)
fi
if [ "${SOURCER_WEB_MODE:-0}" = "1" ]; then
  compose_files+=(-f docker-compose.web.yml)
fi
docker compose "${compose_files[@]}" up --build
