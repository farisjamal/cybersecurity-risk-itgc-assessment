param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^SNAP-[A-Z0-9-]+$')]
    [string]$SnapshotId,
    [string]$EdgePath = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
)

$ErrorActionPreference = 'Stop'
$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$outputRoot = (Resolve-Path -LiteralPath (Join-Path $workspace 'outputs\artifacts')).Path
$bundle = (Resolve-Path -LiteralPath (Join-Path $outputRoot $SnapshotId)).Path
if (-not $bundle.StartsWith($outputRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsafe artifact bundle path: $bundle"
}
if (-not (Test-Path -LiteralPath $EdgePath -PathType Leaf)) {
    throw "Microsoft Edge was not found at $EdgePath"
}

$runtimeRoot = Join-Path $workspace 'runtime'
New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
$profile = Join-Path $runtimeRoot "edge-pdf-$PID"
New-Item -ItemType Directory -Path $profile -Force | Out-Null

$documents = @(
    @{ Source = 'engagement-brief.html'; Target = 'engagement-brief.pdf' },
    @{ Source = 'executive-report.html'; Target = 'executive-report.pdf' },
    @{ Source = 'presentation.html'; Target = 'executive-presentation.pdf' }
)

try {
    foreach ($document in $documents) {
        $source = (Resolve-Path -LiteralPath (Join-Path $bundle $document.Source)).Path
        $target = Join-Path $bundle $document.Target
        if (Test-Path -LiteralPath $target) {
            throw "Refusing to overwrite existing PDF: $target"
        }
        $uri = ([System.Uri]$source).AbsoluteUri
        $arguments = @(
            '--headless=new',
            '--disable-gpu',
            '--no-pdf-header-footer',
            "--user-data-dir=$profile",
            "--print-to-pdf=$target",
            $uri
        )
        $process = Start-Process -FilePath $EdgePath -ArgumentList $arguments -Wait -PassThru -WindowStyle Hidden
        if ($process.ExitCode -ne 0) {
            throw "Edge PDF rendering failed for $($document.Source) with exit code $($process.ExitCode)"
        }
        $rendered = Get-Item -LiteralPath $target
        if ($rendered.Length -eq 0) {
            throw "Edge produced an empty PDF for $($document.Source)"
        }
    }

    $artifacts = foreach ($document in $documents) {
        $path = Get-Item -LiteralPath (Join-Path $bundle $document.Target)
        [ordered]@{
            path = $path.Name
            sha256 = (Get-FileHash -LiteralPath $path.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            size = $path.Length
            source_html = $document.Source
            classification = 'sanitized_portfolio_artifact'
        }
    }
    $manifest = [ordered]@{
        schema_version = '1.0'
        snapshot_id = $SnapshotId
        rendered_at = (Get-Date).ToUniversalTime().ToString('o')
        renderer = "Microsoft Edge $((Get-Item -LiteralPath $EdgePath).VersionInfo.ProductVersion)"
        artifacts = @($artifacts)
        limitations = @(
            'PDFs are local derivatives of manifest-listed HTML artifacts.',
            'Visual inspection is required before distribution.',
            'The rendering environment is recorded but is not independently attested.'
        )
    }
    $manifestPath = Join-Path $bundle 'pdf-render-manifest.json'
    $manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding utf8NoBOM
    Write-Output $manifestPath
}
finally {
    if (Test-Path -LiteralPath $profile) {
        $resolvedProfile = (Resolve-Path -LiteralPath $profile).Path
        $resolvedRuntime = (Resolve-Path -LiteralPath $runtimeRoot).Path
        if (-not $resolvedProfile.StartsWith($resolvedRuntime + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Unsafe Edge profile cleanup path: $resolvedProfile"
        }
        Remove-Item -LiteralPath $resolvedProfile -Recurse -Force
    }
}
