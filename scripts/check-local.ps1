param(
  [switch]$Json
)

$ErrorActionPreference = "SilentlyContinue"
$root = Split-Path -Parent $PSScriptRoot

function Test-Command($Name) {
  $command = Get-Command $Name -ErrorAction SilentlyContinue
  return $null -ne $command
}

function New-Check($Name, $Ok, $Detail) {
  [pscustomobject]@{
    name = $Name
    ok = [bool]$Ok
    detail = $Detail
  }
}

$checks = @()

$pythonPath = Join-Path $root "backend\.venv\Scripts\python.exe"
$checks += New-Check "backend venv" (Test-Path $pythonPath) "backend\.venv\Scripts\python.exe"
if (Test-Path $pythonPath) {
  $pythonVersion = & $pythonPath --version 2>&1
  $checks += New-Check "python" ($LASTEXITCODE -eq 0) ($pythonVersion -join " ")
} else {
  $checks += New-Check "python" (Test-Command "python") "python executable on PATH"
}

$checks += New-Check "backend env" (Test-Path (Join-Path $root "backend\.env")) "backend\.env"
$checks += New-Check "frontend deps" (Test-Path (Join-Path $root "frontend\node_modules")) "frontend\node_modules"

if (Test-Command "node") {
  $nodeVersion = & node --version 2>&1
  $checks += New-Check "node" ($LASTEXITCODE -eq 0) ($nodeVersion -join " ")
} else {
  $checks += New-Check "node" $false "node executable not found"
}

if (Test-Command "npm") {
  $npmVersion = & npm --version 2>&1
  $checks += New-Check "npm" ($LASTEXITCODE -eq 0) ($npmVersion -join " ")
} else {
  $checks += New-Check "npm" $false "npm executable not found"
}

if (Test-Command "bitcoin-cli") {
  $bitcoinCliVersion = & bitcoin-cli --version 2>&1
  $checks += New-Check "bitcoin-cli" ($LASTEXITCODE -eq 0) (($bitcoinCliVersion | Select-Object -First 1) -join " ")
} else {
  $checks += New-Check "bitcoin-cli" $false "bitcoin-cli executable not found"
}

$composeDetail = "neither docker compose nor docker-compose found"
$composeOk = $false
if (Test-Command "docker") {
  & docker compose version *> $null
  if ($LASTEXITCODE -eq 0) {
    $composeOk = $true
    $composeDetail = "docker compose"
  }
}
if (-not $composeOk -and (Test-Command "docker-compose")) {
  $composeOk = $true
  $composeDetail = "docker-compose"
}
$checks += New-Check "compose" $composeOk $composeDetail

$allOk = -not ($checks | Where-Object { -not $_.ok })

if ($Json) {
  [pscustomobject]@{
    ok = $allOk
    checks = $checks
  } | ConvertTo-Json -Depth 4
} else {
  foreach ($check in $checks) {
    $mark = if ($check.ok) { "OK" } else { "MISSING" }
    Write-Output ("{0,-8} {1,-14} {2}" -f $mark, $check.name, $check.detail)
  }
}

if (-not $allOk) {
  exit 1
}
