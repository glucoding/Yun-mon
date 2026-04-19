$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $repoRoot "logs/stack-agent.pid"

if (-not (Test-Path $pidFile)) {
    Write-Host "No stack-agent PID file found." -ForegroundColor Yellow
    exit 0
}

$agentPid = Get-Content $pidFile | Select-Object -First 1
if ($agentPid -and (Get-Process -Id $agentPid -ErrorAction SilentlyContinue)) {
    Stop-Process -Id $agentPid -Force
    Write-Host "Stopped stack-agent process $agentPid." -ForegroundColor Green
} else {
    Write-Host "Stack-agent process was not running." -ForegroundColor Yellow
}

Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
