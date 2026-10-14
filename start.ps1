$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker is required. Install Docker Desktop, then run this file again."
    exit 1
}

$provider = $env:LLM_PROVIDER
if ([string]::IsNullOrWhiteSpace($provider) -and (Test-Path -LiteralPath ".env")) {
    $providerLine = Get-Content -LiteralPath ".env" | Where-Object { $_ -match '^\s*LLM_PROVIDER\s*=' } | Select-Object -Last 1
    if ($providerLine -match '^\s*LLM_PROVIDER\s*=\s*(.*?)\s*$') {
        $provider = $Matches[1]
    }
}
if ([string]::IsNullOrWhiteSpace($provider)) { $provider = "gemini" }
$provider = $provider.Trim().ToLowerInvariant()

docker compose --profile ollama down --remove-orphans

if ($provider -eq "ollama") {
    docker compose --profile ollama up -d --build --wait ollama
    docker compose --profile ollama run --rm ollama-model
    docker compose --profile ollama up -d --build --wait app
    Write-Host "Simple RAG is using the local Ollama provider."
    Write-Host "The first start downloads the Ollama model and may take a few minutes."
} elseif ($provider -in @("gemini", "google", "google-ai-studio")) {
    docker compose up -d --build --wait
    Write-Host "Simple RAG is using the Google AI Studio Gemini provider."
} else {
    throw "Unsupported LLM_PROVIDER=$provider. Use ollama or gemini."
}

Write-Host ""
Write-Host "Simple RAG is starting at http://localhost:8501"
Start-Process "http://localhost:8501"
