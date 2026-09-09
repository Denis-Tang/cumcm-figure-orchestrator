[CmdletBinding()]
param(
    [string]$Version = '0.8.2',
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..')).Path,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$projectPath = [IO.Path]::GetFullPath($ProjectRoot)
$toolsPath = [IO.Path]::GetFullPath((Join-Path $projectPath '.tools'))
$binPath = Join-Path $toolsPath 'bin'
$target = Join-Path $binPath 'd2.exe'

if ((Test-Path -LiteralPath $target) -and -not $Force) {
    Write-Output "D2 already exists: $target"
    & $target version
    exit 0
}

$releaseName = "d2-v$Version-windows-amd64.tar.gz"
$releaseBase = "https://github.com/d2lang/d2/releases/download/v$Version"
$temporaryRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$temporaryPath = [IO.Path]::GetFullPath((Join-Path $temporaryRoot ("cumcm-d2-" + [guid]::NewGuid().ToString('N'))))
if (-not $temporaryPath.StartsWith($temporaryRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing unsafe temporary path: $temporaryPath"
}

try {
    New-Item -ItemType Directory -Path $temporaryPath | Out-Null
    $archive = Join-Path $temporaryPath $releaseName
    $sums = Join-Path $temporaryPath 'SHA256SUMS'
    Invoke-WebRequest -Uri "$releaseBase/$releaseName" -OutFile $archive
    Invoke-WebRequest -Uri "$releaseBase/SHA256SUMS" -OutFile $sums

    $sumLine = Get-Content -LiteralPath $sums | Where-Object { $_ -match [regex]::Escape($releaseName) } | Select-Object -First 1
    if (-not $sumLine) {
        throw "No checksum entry for $releaseName"
    }
    $expected = ($sumLine -split '\s+')[0].ToLowerInvariant()
    $actual = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $expected) {
        throw "D2 archive checksum mismatch: expected $expected, got $actual"
    }

    $expanded = Join-Path $temporaryPath 'expanded'
    New-Item -ItemType Directory -Path $expanded | Out-Null
    & tar.exe -xzf $archive -C $expanded
    if ($LASTEXITCODE -ne 0) {
        throw "tar.exe failed with exit code $LASTEXITCODE"
    }
    $binary = Get-ChildItem -LiteralPath $expanded -Filter 'd2.exe' -File -Recurse | Select-Object -First 1
    if (-not $binary) {
        throw 'd2.exe not found in verified archive'
    }
    New-Item -ItemType Directory -Path $binPath -Force | Out-Null
    Copy-Item -LiteralPath $binary.FullName -Destination $target -Force:$Force
    Write-Output "Installed verified D2 binary: $target"
    Write-Output "SHA256: $actual"
    & $target version
}
finally {
    if (Test-Path -LiteralPath $temporaryPath) {
        $resolvedTemporary = [IO.Path]::GetFullPath($temporaryPath)
        if (-not $resolvedTemporary.StartsWith($temporaryRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing unsafe cleanup path: $resolvedTemporary"
        }
        Remove-Item -LiteralPath $resolvedTemporary -Recurse -Force
    }
}

