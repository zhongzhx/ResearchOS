$ErrorActionPreference = "Stop"

$workspaceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$apiScript = Join-Path $workspaceRoot "backend\research_agent_runtime\scripts\research_agent_api.py"
$auraRuntime = Join-Path $workspaceRoot "runtime\AURA Research.exe"
$envFile = Join-Path $workspaceRoot ".env"
$defaultAgentRoot = Join-Path $workspaceRoot "agent_data"
$agentRoot = if ($env:RESEARCHOS_AGENT_ROOT) { $env:RESEARCHOS_AGENT_ROOT } else { $defaultAgentRoot }
$hostName = if ($env:RESEARCHOS_HOST) { $env:RESEARCHOS_HOST } else { "127.0.0.1" }
$port = if ($env:RESEARCHOS_PORT) { [int]$env:RESEARCHOS_PORT } else { 8765 }
$healthUrl = "http://$hostName`:$port/health"

function Test-ApiReady {
  param([string]$Url)
  try {
    $response = Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 3
    return $response.status -eq "ok"
  } catch {
    return $false
  }
}

if (-not (Test-Path $apiScript)) {
  throw "Missing API script: $apiScript"
}

New-Item -ItemType Directory -Path $agentRoot -Force | Out-Null
if (Test-Path $envFile) {
  $env:RESEARCHOS_ENV_FILE = $envFile
}

if (Test-ApiReady -Url $healthUrl) {
  Write-Output "ResearchOS API already running at $healthUrl"
  exit 0
}

$launcher = if (Test-Path $auraRuntime) { $auraRuntime } else { "py" }
Start-Process -FilePath $launcher -ArgumentList @($apiScript, "--host", $hostName, "--port", "$port", "--agent-root", $agentRoot) -WorkingDirectory $workspaceRoot | Out-Null

$ready = $false
for ($attempt = 0; $attempt -lt 60; $attempt++) {
  Start-Sleep -Milliseconds 500
  if (Test-ApiReady -Url $healthUrl) {
    $ready = $true
    break
  }
}

if (-not $ready) {
  throw "ResearchOS API did not become ready at $healthUrl"
}

Write-Output "ResearchOS API is running at $healthUrl"
