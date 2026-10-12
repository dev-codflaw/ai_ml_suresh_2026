#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Install Docker Desktop, then run this file again."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose is required. Update Docker Desktop, then run this file again."
  exit 1
fi

docker compose up -d --build --wait

echo ""
echo "Simple RAG is starting at http://localhost:${APP_HOST_PORT:-8501}"
echo "The first start downloads the Ollama model and may take a few minutes."
