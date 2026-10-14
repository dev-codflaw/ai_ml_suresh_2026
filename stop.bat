@echo off
cd /d "%~dp0"
docker compose --profile ollama down --remove-orphans
pause
