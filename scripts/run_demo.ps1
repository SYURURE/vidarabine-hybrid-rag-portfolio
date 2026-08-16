param(
    [string]$Question = "デモ注射剤Vと仮想薬Aの組合せについて教えて",
    [switch]$UseOllama
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$App = Join-Path $ProjectRoot "src\vidarabine_rag.py"

$Arguments = @($App, "answer", $Question)
if ($UseOllama) {
    $Arguments += "--use-ollama"
}

python @Arguments
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

python $App evaluate
exit $LASTEXITCODE
