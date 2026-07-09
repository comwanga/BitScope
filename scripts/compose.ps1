param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$ComposeArgs
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root "backend\.env.docker"
$dockerConfig = Join-Path $root ".docker-local"

function Import-EnvFile($Path) {
  if (-not (Test-Path $Path)) {
    return
  }

  foreach ($line in Get-Content -LiteralPath $Path) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith("#")) {
      continue
    }

    $separator = $trimmed.IndexOf("=")
    if ($separator -le 0) {
      continue
    }

    $name = $trimmed.Substring(0, $separator).Trim()
    $value = $trimmed.Substring($separator + 1).Trim()
    if ($value.Length -ge 2 -and (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'")))) {
      $value = $value.Substring(1, $value.Length - 2)
    }

    if ($null -eq [Environment]::GetEnvironmentVariable($name, "Process")) {
      [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
  }
}

function Get-ComposeCommand {
  $dockerCompose = Get-Command docker-compose -ErrorAction SilentlyContinue
  if ($dockerCompose) {
    return @("docker-compose")
  }

  $docker = Get-Command docker -ErrorAction SilentlyContinue
  if ($docker) {
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & docker compose version *> $null
    $composeExitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousPreference
    if ($composeExitCode -eq 0) {
      return @("docker", "compose")
    }
  }

  throw "Neither 'docker compose' nor 'docker-compose' is available on PATH."
}

Import-EnvFile $envFile
if (-not [Environment]::GetEnvironmentVariable("DOCKER_CONFIG", "Process")) {
  New-Item -ItemType Directory -Force -Path $dockerConfig | Out-Null
  [Environment]::SetEnvironmentVariable("DOCKER_CONFIG", $dockerConfig, "Process")
}

if (-not $ComposeArgs -or $ComposeArgs.Count -eq 0) {
  $ComposeArgs = @("up", "--build")
}

$composeCommand = @(Get-ComposeCommand)
Push-Location $root
try {
  $previousPreference = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  if ($composeCommand.Count -eq 2) {
    & $composeCommand[0] $composeCommand[1] @ComposeArgs
  } else {
    & $composeCommand[0] @ComposeArgs
  }
  $composeExitCode = $LASTEXITCODE
  $ErrorActionPreference = $previousPreference
  exit $composeExitCode
} finally {
  Pop-Location
}
