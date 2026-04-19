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

function Get-DotEnvValue {
    param(
        [string]$Key,
        [string]$DefaultValue
    )

    $envFile = Join-Path $repoRoot ".env"
    if (Test-Path $envFile) {
        $line = Get-Content $envFile | Where-Object { $_ -match "^\s*$Key=" } | Select-Object -First 1
        if ($line) {
            return ($line -split "=", 2)[1].Trim()
        }
    }

    return $DefaultValue
}

Set-Location $repoRoot
Write-Host "Starting Yun-mon monitoring stack..." -ForegroundColor Cyan
$stackAgentScript = Join-Path $PSScriptRoot "start-stack-agent.ps1"
if (Test-Path $stackAgentScript) {
    & $stackAgentScript
}

$env:DOCKER_BUILDKIT = "0"
$env:COMPOSE_DOCKER_CLI_BUILD = "0"

Invoke-NativeCommand { docker compose up -d --build }
Invoke-NativeCommand { docker compose ps }

Remove-Item Env:DOCKER_BUILDKIT -ErrorAction SilentlyContinue
Remove-Item Env:COMPOSE_DOCKER_CLI_BUILD -ErrorAction SilentlyContinue

$grafanaPort = Get-DotEnvValue -Key "GRAFANA_HOST_PORT" -DefaultValue "13000"
$demoServicePort = Get-DotEnvValue -Key "DEMO_SERVICE_HOST_PORT" -DefaultValue "18080"

Write-Host "" 
Write-Host "Access URLs:" -ForegroundColor Green
Write-Host "Grafana      http://localhost:$grafanaPort"
Write-Host "Prometheus   http://localhost:9090"
Write-Host "Alertmanager http://localhost:9093"
Write-Host "Loki         http://localhost:3100"
Write-Host "Demo Service http://localhost:$demoServicePort"
