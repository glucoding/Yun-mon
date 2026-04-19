$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$logsDir = Join-Path $repoRoot "logs"
$pidFile = Join-Path $logsDir "stack-agent.pid"
$stdoutLog = Join-Path $logsDir "stack-agent.out.log"
$stderrLog = Join-Path $logsDir "stack-agent.err.log"

function Get-DotEnvValue {
    param(
        [string]$Key,
        [string]$DefaultValue
    )

    $envFile = Join-Path $repoRoot ".env"
    if (Test-Path $envFile) {
        $line = Get-Content $envFile | Where-Object { $_ -match "^\s*$Key=" } | Select-Object -First 1
        if ($line) {
            return ($line -split "=", 2)[1].Trim('"')
        }
    }

    return $DefaultValue
}

function Test-ListeningPort {
    param([int]$Port)
    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    return $null -ne $connection
}

New-Item -ItemType Directory -Path $logsDir -Force | Out-Null

$agentUrl = Get-DotEnvValue -Key "STACK_AGENT_BASE_URL" -DefaultValue "http://host.docker.internal:19090"
$token = Get-DotEnvValue -Key "STACK_AGENT_SHARED_TOKEN" -DefaultValue "yunmon-local-agent-token"
$uri = [uri]$agentUrl
$port = if ($uri.Port -gt 0) { $uri.Port } else { 19090 }

if (Test-ListeningPort -Port $port) {
    Write-Host "Yun-mon stack-agent is already listening on port $port." -ForegroundColor Yellow
    exit 0
}

$env:STACK_AGENT_WORKSPACE = $repoRoot
$env:STACK_AGENT_HTTP_HOST = "0.0.0.0"
$env:STACK_AGENT_HTTP_PORT = "$port"
$env:STACK_AGENT_SHARED_TOKEN = $token

$process = Start-Process -FilePath "py" `
    -ArgumentList @("-3", (Join-Path $repoRoot "apps/stack-agent/agent.py")) `
    -WorkingDirectory $repoRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -PassThru

Set-Content -Path $pidFile -Value $process.Id

$deadline = (Get-Date).AddSeconds(20)
do {
    Start-Sleep -Milliseconds 500
    if (Test-ListeningPort -Port $port) {
        Write-Host "Yun-mon stack-agent started on port $port." -ForegroundColor Green
        Write-Host "PID: $($process.Id)"
        Write-Host "Logs: $stdoutLog"
        exit 0
    }
} while ((Get-Date) -lt $deadline)

throw "Stack-agent did not start listening on port $port within the timeout window."
