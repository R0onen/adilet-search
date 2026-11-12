param(
    [switch]$Full,
    [switch]$LlmRewrite,
    [string[]]$Models = @('e5', 'qwen3', 'bge_m3', 'embeddinggemma2'),
    [string]$RevisionsFrom
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
    $kind = if ($Full) { 'full' } else { 'pilot' }
    $outputDir = if ($Full) { '/tmp/research/full' } else { '/tmp/research/out' }
    & docker exec adilet-final-ml-service-1 mkdir -p /tmp/research/data /tmp/research/eval /tmp/research/out
    & docker exec adilet-final-ml-service-1 mkdir -p $outputDir
    & docker cp ml/scripts/research_benchmark.py adilet-final-ml-service-1:/tmp/research/run.py
    & docker cp ml/scripts/research_core.py adilet-final-ml-service-1:/tmp/research/research_core.py
    & docker cp data/processed/chunks.parquet adilet-final-ml-service-1:/tmp/research/data/chunks.parquet
    foreach ($file in @('queries.jsonl','qrels.jsonl','splits.json')) {
        & docker cp "data/eval/$file" "adilet-final-ml-service-1:/tmp/research/eval/$file"
    }
    $runnerArgs = @('exec','adilet-final-ml-service-1','python','/tmp/research/run.py',
        '--data','/tmp/research/data','--eval','/tmp/research/eval','--out',$outputDir,
        '--vector-cache','/tmp/research/out')
    if (-not $Full) { $runnerArgs += @('--pilot-per-language','4') }
    if ($LlmRewrite) { $runnerArgs += '--llm-rewrite' }
    $runnerArgs += @('--models') + $Models
    if ($RevisionsFrom) {
        & docker cp $RevisionsFrom adilet-final-ml-service-1:/tmp/research/revisions.json
        if ($LASTEXITCODE -ne 0) { throw 'Cannot copy frozen checkpoint revisions.' }
        $runnerArgs += @('--revisions-from', '/tmp/research/revisions.json')
    }
    & docker @runnerArgs
    $runExitCode = $LASTEXITCODE
    New-Item -ItemType Directory -Force 'data/research/current' | Out-Null
    & docker cp "adilet-final-ml-service-1:${outputDir}/." data/research/current/
    if (Test-Path 'data/research/current/results.json') {
        New-Item -ItemType Directory -Force "ml/experiments/research-$kind" | Out-Null
        Copy-Item 'data/research/current/results.json' "ml/experiments/research-$kind/results.json"
        $completed = (Get-Content 'data/research/current/results.json' -Raw | ConvertFrom-Json).methods
        foreach ($method in $completed.PSObject.Properties.Name) {
            Copy-Item "data/research/current/${method}_rankings.json" "ml/experiments/research-$kind/"
        }
    }
    if ($runExitCode -ne 0) { throw 'Research run failed; inspect logs and partial artifacts.' }
} finally { Pop-Location }
