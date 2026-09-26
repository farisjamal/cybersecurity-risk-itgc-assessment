[CmdletBinding()]
param(
    [switch]$SkipIntegration,
    [switch]$SkipCompose
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$env:UV_CACHE_DIR = Join-Path $root ".uv-cache"

function Invoke-Gate {
    param([string]$Name, [scriptblock]$Command)
    Write-Host "`n== $Name ==" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Name failed with exit code $LASTEXITCODE." }
}

Push-Location $root
try {
    Invoke-Gate "Locked environment" { uv sync --frozen --all-groups }
    Invoke-Gate "Ruff lint" { uv run ruff check . }
    Invoke-Gate "Ruff format" { uv run ruff format --check . }
    Invoke-Gate "Strict type checking" { uv run python -m mypy src }
    Invoke-Gate "Locked dependency audit" {
        uv run python -m pip_audit --requirement requirements.lock --disable-pip --progress-spinner off
    }
    Invoke-Gate "Tests and coverage" {
        uv run pytest -p no:cacheprovider --basetemp "runtime/pytest-coverage-$PID" -m "not slow"
    }
    Invoke-Gate "Assessment schema" { uv run python -m cyber_assess assess validate --engagement ENG-001 }
    Invoke-Gate "Finding schema" { uv run python -m cyber_assess findings validate --engagement ENG-001 }
    Invoke-Gate "Markdown links" { & "$PSScriptRoot/check-links.ps1" }

    if (-not $SkipIntegration) {
        Invoke-Gate "Integration and acceptance tests" {
            uv run pytest -p no:cacheprovider --basetemp "runtime/pytest-integration-$PID" -m "integration or acceptance" --no-cov
        }
    }

    if (-not $SkipCompose) {
        if (-not (Test-Path ".env")) { throw "Compose validation requires a populated .env file." }
        Invoke-Gate "Compose model" { docker compose --env-file .env config --quiet }
    }

    if (Test-Path ".git") {
        $forbidden = @(git -c "safe.directory=$root" ls-files | Where-Object {
            $_ -match '(^|/)(\.env|runtime|outputs)/' -or $_ -match '\.(pem|key)$'
        })
        if ($forbidden.Count -gt 0) {
            throw "Repository hygiene failed; forbidden tracked paths: $($forbidden -join ', ')"
        }
    }
    Write-Host "`nAll requested repository gates passed." -ForegroundColor Green
}
finally {
    Pop-Location
}
