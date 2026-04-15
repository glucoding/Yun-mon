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

Write-Host "Yun-mon stack stopped." -ForegroundColor Green

