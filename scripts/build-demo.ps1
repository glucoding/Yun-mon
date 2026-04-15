$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$appRoot = Join-Path $repoRoot "apps/demo-service"

Set-Location $appRoot
mvn -B clean package

