# P0-4：默认仅监听 127.0.0.1。如要让容器内的 control-plane 通过 host.docker.internal 访问,
# 请显式设置 STACK_AGENT_HTTP_HOST=0.0.0.0,并在文档中明确风险。
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
$token = Get-DotEnvValue -Key "STACK_AGENT_SHARED_TOKEN" -DefaultValue ""
$bindHost = Get-DotEnvValue -Key "STACK_AGENT_HTTP_HOST" -DefaultValue "127.0.0.1"

if ([string]::IsNullOrWhiteSpace($token) -or $token.Length -lt 16) {
    Write-Error "STACK_AGENT_SHARED_TOKEN 未配置或长度不足 16,请在控制台保存配置后再启动 stack-agent。"
    exit 2
}

$uri = [uri]$agentUrl
$port = if ($uri.Port -gt 0) { $uri.Port } else { 19090 }

if (Test-ListeningPort -Port $port) {
    Write-Host "Yun-mon stack-agent 已经在端口 $port 监听。" -ForegroundColor Yellow
    exit 0
}

if ($bindHost -eq "0.0.0.0") {
    Write-Warning "stack-agent 将绑定 0.0.0.0,请确认本机有防火墙隔离或反向代理收口。"
}

$env:STACK_AGENT_WORKSPACE = $repoRoot
$env:STACK_AGENT_HTTP_HOST = $bindHost
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
        Write-Host "Yun-mon stack-agent 已启动,绑定 $bindHost`:$port。" -ForegroundColor Green
        Write-Host "PID: $($process.Id)"
        Write-Host "日志: $stdoutLog"
        exit 0
    }
} while ((Get-Date) -lt $deadline)

throw "stack-agent 在超时窗口内未开始监听 $port,请检查 $stderrLog。"
