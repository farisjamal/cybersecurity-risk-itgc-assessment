[CmdletBinding()]
param(
    [switch]$Json
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$env:UV_CACHE_DIR = Join-Path $root ".uv-cache"
$checks = [System.Collections.Generic.List[object]]::new()

function Add-Check {
    param([string]$Name, [bool]$Passed, [string]$Detail, [bool]$Required = $true)
    $checks.Add([pscustomobject]@{
        name = $Name
        passed = $Passed
        required = $Required
        detail = $Detail
    })
}

function Test-Command {
    param([string]$Name)
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

Push-Location $root
try {
    $uvPresent = Test-Command "uv"
    Add-Check "uv" $uvPresent $(if ($uvPresent) { (uv --version) } else { "Install uv 0.11 or later." })

    if ($uvPresent) {
        $pythonVersion = (uv run --no-sync python -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" 2>$null)
        $pythonOk = $LASTEXITCODE -eq 0 -and $pythonVersion -match '^3\.12\.'
        Add-Check "python" $pythonOk $(if ($pythonOk) { "Python $pythonVersion" } else { "Python 3.12 is required." })
    }
    else {
        Add-Check "python" $false "Cannot resolve the managed Python runtime without uv."
    }

    $dockerPresent = Test-Command "docker"
    Add-Check "docker-cli" $dockerPresent $(if ($dockerPresent) { "Docker CLI found." } else { "Install Docker Desktop or Docker Engine." })
    if ($dockerPresent) {
        docker info --format '{{.ServerVersion}}' *> $null
        $engineOk = $LASTEXITCODE -eq 0
        Add-Check "docker-engine" $engineOk $(if ($engineOk) { "Docker engine is reachable." } else { "Start Docker Desktop/Engine." })

        docker compose version *> $null
        Add-Check "docker-compose" ($LASTEXITCODE -eq 0) "Docker Compose v2 is required."
    }

    Add-Check "environment" (Test-Path ".env" -PathType Leaf) "Copy .env.example to .env and replace every CHANGE_ME value."
    if (Test-Path ".env" -PathType Leaf) {
        $hasPlaceholder = [bool](Select-String -Path ".env" -Pattern 'CHANGE_ME' -Quiet)
        Add-Check "environment-placeholders" (-not $hasPlaceholder) "No secret values are displayed by this check."
    }

    foreach ($directory in @("runtime", "outputs", "portfolio")) {
        if (-not (Test-Path $directory)) { New-Item -ItemType Directory -Path $directory | Out-Null }
        $probe = Join-Path $directory ".write-probe-$PID"
        try {
            [System.IO.File]::WriteAllText((Join-Path $root $probe), "probe")
            Remove-Item -LiteralPath (Join-Path $root $probe) -Force
            Add-Check "writable-$directory" $true "$directory is writable."
        }
        catch {
            Add-Check "writable-$directory" $false "$directory is not writable."
        }
    }

    $listener = $null
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 8000)
        $listener.Start()
        Add-Check "port-8000" $true "127.0.0.1:8000 is available."
    }
    catch {
        Add-Check "port-8000" $false "127.0.0.1:8000 is already in use."
    }
    finally {
        if ($null -ne $listener) { $listener.Stop() }
    }

    $freeGiB = [math]::Round((Get-PSDrive -Name (Split-Path $root -Qualifier).TrimEnd(':')).Free / 1GB, 1)
    Add-Check "disk-space" ($freeGiB -ge 10) "$freeGiB GiB free; the planning minimum is 10 GiB."

    foreach ($path in @("PRD.md", "assessment/engagement.yaml", "assessment/controls.yaml", "docs/source-register.md")) {
        Add-Check "source-$path" (Test-Path $path -PathType Leaf) "$path must exist."
    }

    $failed = @($checks | Where-Object { $_.required -and -not $_.passed })
    if ($Json) {
        [pscustomobject]@{ ok = $failed.Count -eq 0; checks = $checks } | ConvertTo-Json -Depth 4
    }
    else {
        $checks | Format-Table @{Label="Status"; Expression={if ($_.passed) {"PASS"} else {"FAIL"}}}, name, detail -AutoSize
    }
    if ($failed.Count -gt 0) { exit 3 }
    exit 0
}
finally {
    Pop-Location
}
