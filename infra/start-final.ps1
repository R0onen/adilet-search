param(
    [ValidateSet('sample', 'processed')][string]$Corpus = 'sample',
    [switch]$Index,
    [switch]$Gpu,
    [ValidateRange(1, 32)][int]$InferenceWorkers = 4,
    [ValidateRange(1, 32)][int]$CpuThreads = 1,
    [ValidateRange(1, 100)][int]$RerankCandidates = 3
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
Push-Location $repoRoot
try {
    if (-not (Test-Path '.env.final')) {
        $secretBytes = New-Object byte[] 32
        [System.Security.Cryptography.RandomNumberGenerator]::Fill($secretBytes)
        $secret = [Convert]::ToBase64String($secretBytes)
        $saltBytes = New-Object byte[] 32
        [System.Security.Cryptography.RandomNumberGenerator]::Fill($saltBytes)
        $sessionSalt = [Convert]::ToBase64String($saltBytes)
        $lines = @(
            'ML_SERVICE_URL=http://ml-service:8001',
            'BACKEND_PORT=18000', 'ML_SERVICE_PORT=18001',
            'POSTGRES_PORT=55432', 'QDRANT_PORT=16333', 'QDRANT_GRPC_PORT=16334',
            'FRONTEND_PORT=18080', 'PROMETHEUS_PORT=19090', 'GRAFANA_PORT=13000',
            "GRAFANA_ADMIN_PASSWORD=$secret", "SESSION_SALT=$sessionSalt",
            "ADILET_ML_INFERENCE_WORKERS=$InferenceWorkers",
            "ADILET_ML_CPU_THREADS=$CpuThreads",
            "SEARCH_RERANK_TOP_N=$RerankCandidates",
            'ADILET_ML_GENERATOR_MODE=fallback'
        )
        [IO.File]::WriteAllLines((Join-Path $repoRoot '.env.final'), $lines)
    }
    $composeArgs = @('compose', '-p', 'adilet-final', '--env-file', '.env.final',
        '-f', 'docker-compose.yml', '-f', 'docker-compose.final.yml')
    if ($Gpu) { $composeArgs += @('-f', 'docker-compose.gpu.yml') }
    $composeArgs += @('--profile', 'ml')
    & docker @composeArgs up -d --build
    if ($LASTEXITCODE -ne 0) { throw 'Compose failed; inspect the build output.' }
    if ($Index) {
        # The indexer requires ML models to finish loading first.
        & docker @composeArgs up -d --wait ml-service
        if ($LASTEXITCODE -ne 0) { throw 'ML service did not become healthy.' }
        & docker @composeArgs exec -T backend python -m indexer --data-dir "/data/$Corpus"
        if ($LASTEXITCODE -ne 0) { throw 'Indexing failed; the previous index is retained.' }
    }
    Write-Host 'UI: http://127.0.0.1:18080 | API: http://127.0.0.1:18000/api/v1/docs'
    Write-Host 'Grafana: http://127.0.0.1:13000 | Prometheus: http://127.0.0.1:19090'
    Write-Host 'Grafana username: admin; password is stored in ignored .env.final.'
} finally {
    Pop-Location
}
