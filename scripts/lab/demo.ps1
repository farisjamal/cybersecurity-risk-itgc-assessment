[CmdletBinding()]
param(
    [ValidateSet("S01", "S02", "S03", "S04", "S05", "S06")]
    [string]$Scenario = "S01",
    [int]$Seed = 42,
    [switch]$KeepRunning
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$env:UV_CACHE_DIR = Join-Path $root ".uv-cache"

function Invoke-Assess {
    param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments)
    & uv run python -m cyber_assess @Arguments
    if ($LASTEXITCODE -ne 0) { throw "cyber_assess $($Arguments -join ' ') failed ($LASTEXITCODE)." }
}

Push-Location $root
try {
    & "$PSScriptRoot/doctor.ps1"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Invoke-Assess doctor
    Invoke-Assess lab up
    Invoke-Assess lab seed --seed $Seed
    Invoke-Assess scenario run --id $Scenario

    Write-Host ""
    Write-Host "Open http://127.0.0.1:8000 and follow docs/demo.md." -ForegroundColor Green
    Write-Host "The baseline is preserved. Run remediation/retest with the run ID printed above."
}
finally {
    if (-not $KeepRunning) {
        & uv run python -m cyber_assess lab stop
    }
    Pop-Location
}
