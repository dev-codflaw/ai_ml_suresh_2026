@echo off
setlocal
cd /d "%~dp0"

where docker >nul 2>nul
if errorlevel 1 (
  echo Docker is required. Install Docker Desktop, then run this file again.
  pause
  exit /b 1
)

docker compose up -d --build --wait
if errorlevel 1 (
  pause
  exit /b 1
)

echo.
echo Simple RAG is starting at http://localhost:8501
echo The first start downloads the Ollama model and may take a few minutes.
start "" http://localhost:8501
pause
