$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker is required. Install Docker Desktop, then run this file again."
    exit 1
}

docker compose up -d --build --wait
Write-Host ""
Write-Host "Simple RAG is starting at http://localhost:8501"
Write-Host "The first start downloads the Ollama model and may take a few minutes."
Start-Process "http://localhost:8501"
