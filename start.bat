@echo off
setlocal
cd /d "%~dp0"

where docker >nul 2>nul
if errorlevel 1 (
  echo Docker is required. Install Docker Desktop, then run this file again.
  pause
  exit /b 1
)

set "LLM_PROVIDER_VALUE=%LLM_PROVIDER%"
if not defined LLM_PROVIDER_VALUE set "LLM_PROVIDER_VALUE=gemini"
if exist .env (
  for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if /I "%%A"=="LLM_PROVIDER" set "LLM_PROVIDER_VALUE=%%B"
  )
)

docker compose --profile ollama down --remove-orphans

if /I "%LLM_PROVIDER_VALUE%"=="ollama" (
  docker compose --profile ollama up -d --build --wait ollama
  if errorlevel 1 goto failure
  docker compose --profile ollama run --rm ollama-model
  if errorlevel 1 goto failure
  docker compose --profile ollama up -d --build --wait app
  if errorlevel 1 goto failure
  echo Simple RAG is using the local Ollama provider.
  echo The first start downloads the Ollama model and may take a few minutes.
) else if /I "%LLM_PROVIDER_VALUE%"=="gemini" (
  docker compose up -d --build --wait
  if errorlevel 1 goto failure
  echo Simple RAG is using the Google AI Studio Gemini provider.
) else (
  echo Unsupported LLM_PROVIDER=%LLM_PROVIDER_VALUE%. Use ollama or gemini.
  goto failure
)

echo.
echo Simple RAG is starting at http://localhost:8501
start "" http://localhost:8501
pause
exit /b 0

:failure
pause
exit /b 1
