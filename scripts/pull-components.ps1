$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

function Invoke-NativeCommand {
    param(
        [scriptblock]$Command
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Native command failed with exit code $LASTEXITCODE"
    }
}

Set-Location $repoRoot
Write-Host "[1/3] Pull monitoring images..." -ForegroundColor Cyan
Invoke-NativeCommand { docker compose pull prometheus alertmanager loki promtail grafana cadvisor }

$env:DOCKER_BUILDKIT = "0"
$env:COMPOSE_DOCKER_CLI_BUILD = "0"

Write-Host "[2/3] Download demo-service Maven dependencies..." -ForegroundColor Cyan
Set-Location (Join-Path $repoRoot "apps/demo-service")
Invoke-NativeCommand { mvn -B dependency:go-offline }

Set-Location $repoRoot
Write-Host "[3/3] Prebuild demo-service image..." -ForegroundColor Cyan
Invoke-NativeCommand { docker compose build demo-service }

Remove-Item Env:DOCKER_BUILDKIT -ErrorAction SilentlyContinue
Remove-Item Env:COMPOSE_DOCKER_CLI_BUILD -ErrorAction SilentlyContinue

Write-Host "Components downloaded successfully." -ForegroundColor Green
