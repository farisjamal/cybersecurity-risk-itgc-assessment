[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Push-Location $root
try {
    $markdownFiles = if (Test-Path ".git") {
        @(
            git -c "safe.directory=$root" ls-files "*.md"
            git -c "safe.directory=$root" ls-files --others --exclude-standard "*.md"
        ) | Sort-Object -Unique
    }
    else {
        @(Get-ChildItem -Recurse -File -Filter "*.md" | ForEach-Object { $_.FullName })
    }

    $failures = [System.Collections.Generic.List[string]]::new()
    $pattern = [regex]'!?(?:\[[^\]]*\])\((?<target>[^)]+)\)'
    foreach ($file in $markdownFiles) {
        $content = Get-Content -Raw -LiteralPath $file
        foreach ($match in $pattern.Matches($content)) {
            $target = $match.Groups['target'].Value.Trim().Trim('<', '>')
            if ($target -match '^(?:https?://|mailto:|#)' -or [string]::IsNullOrWhiteSpace($target)) { continue }
            $pathPart = [uri]::UnescapeDataString(($target -split '#', 2)[0])
            if ([string]::IsNullOrWhiteSpace($pathPart)) { continue }
            $base = Split-Path -Parent (Resolve-Path -LiteralPath $file)
            $resolved = Join-Path $base $pathPart
            if (-not (Test-Path -LiteralPath $resolved)) {
                $failures.Add("${file}: missing local link target '$target'")
            }
        }
    }

    if ($failures.Count -gt 0) {
        $failures | ForEach-Object { Write-Error $_ }
        exit 4
    }
    Write-Host "Validated local Markdown links in $($markdownFiles.Count) files."
}
finally {
    Pop-Location
}
