param(
    [switch]$RemoveVolumes
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

Set-Location $repoRoot

if ($RemoveVolumes) {
    docker compose down -v
} else {
    docker compose down
}

$stackAgentScript = Join-Path $PSScriptRoot "stop-stack-agent.ps1"
if (Test-Path $stackAgentScript) {
    & $stackAgentScript
}

Write-Host "Yun-mon stack stopped." -ForegroundColor Green
