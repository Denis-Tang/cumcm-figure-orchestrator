[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Source,
    [Parameter(Mandatory = $true)][string]$SvgOut,
    [Parameter(Mandatory = $true)][string]$PngOut,
    [Parameter(Mandatory = $true)][string]$PalettePath,
    [ValidateRange(1, 4)][int]$Scale = 2
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..')).Path
$localD2 = Join-Path $projectRoot '.tools\bin\d2.exe'
$d2 = if (Test-Path -LiteralPath $localD2) { $localD2 } else { (Get-Command d2 -ErrorAction Stop).Source }
$edgeCandidates = @(
    'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
)
$edge = $edgeCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $edge) {
    throw 'Microsoft Edge is required for faithful D2 SVG-to-PNG rendering.'
}

$sourcePath = [IO.Path]::GetFullPath($Source)
$svgPath = [IO.Path]::GetFullPath($SvgOut)
$pngPath = [IO.Path]::GetFullPath($PngOut)
New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($svgPath)) -Force | Out-Null
New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($pngPath)) -Force | Out-Null

$materialized = Join-Path ([IO.Path]::GetDirectoryName($svgPath)) ([IO.Path]::GetFileNameWithoutExtension($svgPath) + '.materialized.d2')
$adapter = Join-Path $PSScriptRoot 'materialize_d2.py'
& py -3.11 $adapter --source $sourcePath --out $materialized --palette ([IO.Path]::GetFullPath($PalettePath))
if ($LASTEXITCODE -ne 0) { throw "D2 palette materialization failed with exit code $LASTEXITCODE" }
$sourcePath = $materialized

& $d2 --layout elk $sourcePath $svgPath
if ($LASTEXITCODE -ne 0) {
    throw "D2 failed with exit code $LASTEXITCODE"
}

$firstLine = Get-Content -LiteralPath $svgPath -TotalCount 1
$viewBox = [regex]::Match($firstLine, 'viewBox="0 0 ([0-9]+) ([0-9]+)"')
if (-not $viewBox.Success) {
    throw 'Could not read D2 SVG dimensions.'
}
$width = [int]$viewBox.Groups[1].Value
$height = [int]$viewBox.Groups[2].Value
$profile = Join-Path $projectRoot '.tools\edge-headless-profile'
New-Item -ItemType Directory -Path $profile -Force | Out-Null
$uri = [Uri]::new($svgPath).AbsoluteUri

& $edge --headless=new --disable-gpu --hide-scrollbars --run-all-compositor-stages-before-draw `
    --force-device-scale-factor=$Scale --window-size="$width,$height" --user-data-dir=$profile `
    --screenshot=$pngPath $uri
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $pngPath)) {
    throw 'Microsoft Edge failed to render the PNG.'
}
if ((Get-Item -LiteralPath $pngPath).Length -lt 1024) {
    throw 'Rendered PNG is unexpectedly small.'
}
Write-Output "Rendered SVG: $svgPath"
Write-Output "Rendered PNG: $pngPath"
Write-Output "Canvas: $width x $height; device scale: $Scale"
