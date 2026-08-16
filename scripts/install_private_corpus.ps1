param(
    [Parameter(Mandatory = $true)]
    [string]$SourceFile
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SourcePath = (Resolve-Path -LiteralPath $SourceFile).Path
$PrivateDirectory = Join-Path $ProjectRoot "data\private"
$DestinationPath = Join-Path $PrivateDirectory "vidarabine_documents.jsonl"

if ([System.IO.Path]::GetExtension($SourcePath) -ne ".jsonl") {
    throw "JSONL file required: $SourcePath"
}

New-Item -ItemType Directory -Force -Path $PrivateDirectory | Out-Null
Copy-Item -LiteralPath $SourcePath -Destination $DestinationPath -Force

Write-Host "Private corpus installed (this folder is ignored by Git):"
Write-Host $DestinationPath
python (Join-Path $ProjectRoot "src\vidarabine_rag.py") inspect
exit $LASTEXITCODE
