$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

docker compose --profile ollama down --remove-orphans
