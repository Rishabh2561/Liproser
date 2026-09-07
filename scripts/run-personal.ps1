$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repositoryRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $python)) {
    throw 'Create the Python environment and install dependencies first.'
}

Write-Host 'Start PostgreSQL and Redis using DATABASE_URL/REDIS_URL from .env, then run these in separate terminals:'
Write-Host "  & '$python' -m uvicorn liproser.main:app --app-dir apps/api --host 127.0.0.1 --port 8000 --reload"
Write-Host "  & '$python' -m arq liproser.worker.WorkerSettings"
Write-Host '  pnpm --filter @liproser/web dev'
