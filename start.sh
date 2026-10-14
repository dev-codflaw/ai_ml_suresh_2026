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

LLM_PROVIDER_VALUE="${LLM_PROVIDER:-}"
if [ -z "$LLM_PROVIDER_VALUE" ] && [ -f .env ]; then
  LLM_PROVIDER_VALUE=$(sed -n 's/^[[:space:]]*LLM_PROVIDER[[:space:]]*=[[:space:]]*//p' .env | tail -n 1)
fi
LLM_PROVIDER_VALUE=$(printf '%s' "$LLM_PROVIDER_VALUE" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')
LLM_PROVIDER_VALUE=${LLM_PROVIDER_VALUE:-gemini}

# Stop a previously selected provider before starting the newly selected one.
docker compose --profile ollama down --remove-orphans

case "$LLM_PROVIDER_VALUE" in
  ollama)
    docker compose --profile ollama up -d --build --wait ollama
    docker compose --profile ollama run --rm ollama-model
    docker compose --profile ollama up -d --build --wait app
    echo "Simple RAG is using the local Ollama provider."
    echo "The first start downloads the Ollama model and may take a few minutes."
    ;;
  gemini|google|google-ai-studio)
    docker compose up -d --build --wait
    echo "Simple RAG is using the Google AI Studio Gemini provider."
    ;;
  *)
    echo "Unsupported LLM_PROVIDER=$LLM_PROVIDER_VALUE. Use ollama or gemini."
    exit 1
    ;;
esac

echo ""
echo "Simple RAG is starting at http://localhost:${APP_HOST_PORT:-8501}"
