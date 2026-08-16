param(
    [string]$DestinationPath = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ProjectName = Split-Path -Leaf $ProjectRoot

if (-not $DestinationPath) {
    $DestinationPath = Join-Path (Split-Path -Parent $ProjectRoot) "vidarabine-hybrid-rag-public.zip"
}
$DestinationPath = [System.IO.Path]::GetFullPath($DestinationPath)
if (Test-Path -LiteralPath $DestinationPath) {
    throw "Destination already exists: $DestinationPath"
}

python (Join-Path $PSScriptRoot "generate_manifest.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python (Join-Path $PSScriptRoot "verify_portfolio.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$StagingBase = Join-Path ([System.IO.Path]::GetTempPath()) ("vidarabine-rag-public-" + [guid]::NewGuid().ToString("N"))
$StagingRoot = Join-Path $StagingBase $ProjectName
New-Item -ItemType Directory -Force -Path $StagingRoot | Out-Null

try {
    $ManifestPath = Join-Path $ProjectRoot "MANIFEST.sha256"
    foreach ($Line in Get-Content -LiteralPath $ManifestPath) {
        if (-not $Line.Trim()) { continue }
        if ($Line -notmatch "^[0-9a-f]{64}  (.+)$") {
            throw "Invalid manifest line: $Line"
        }
        $RelativePath = $Matches[1].Replace("/", [System.IO.Path]::DirectorySeparatorChar)
        $SourcePath = Join-Path $ProjectRoot $RelativePath
        $TargetPath = Join-Path $StagingRoot $RelativePath
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $TargetPath) | Out-Null
        Copy-Item -LiteralPath $SourcePath -Destination $TargetPath
    }
    Copy-Item -LiteralPath $ManifestPath -Destination (Join-Path $StagingRoot "MANIFEST.sha256")
    Compress-Archive -LiteralPath $StagingRoot -DestinationPath $DestinationPath -CompressionLevel Optimal
}
finally {
    $ResolvedStaging = [System.IO.Path]::GetFullPath($StagingBase)
    $ResolvedTemp = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    if ($ResolvedStaging.StartsWith($ResolvedTemp) -and (Test-Path -LiteralPath $ResolvedStaging)) {
        Remove-Item -LiteralPath $ResolvedStaging -Recurse -Force
    }
}

Write-Host "Public ZIP created without data/private:"
Write-Host $DestinationPath
