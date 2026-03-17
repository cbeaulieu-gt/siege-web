# Full rebuild script for Siege Web App
# Usage: .\rebuild.ps1          - rebuild, keep DB
#        .\rebuild.ps1 -Wipe    - rebuild with fresh DB
param(
    [switch]$Wipe
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "=== Stopping containers ===" -ForegroundColor Cyan
docker-compose down

if ($Wipe) {
    Write-Host "=== Removing database volume ===" -ForegroundColor Yellow
    docker volume rm siege-web_postgres_data 2>$null
}

Write-Host "=== Building and starting containers ===" -ForegroundColor Cyan
docker-compose up --build -d

Write-Host "=== Waiting for backend to be ready ===" -ForegroundColor Cyan
do {
    Start-Sleep -Seconds 2
    $ready = docker-compose exec -T backend python -c "print('ok')" 2>$null
} until ($ready -eq "ok")

Write-Host "=== Running migrations ===" -ForegroundColor Cyan
docker-compose exec -T backend alembic upgrade head

Write-Host "=== Seeding database ===" -ForegroundColor Cyan
docker-compose exec -T backend python scripts/seed.py

Write-Host "=== Running Excel import ===" -ForegroundColor Cyan
pip install -q -r scripts/requirements.txt 2>$null
python scripts/import_excel.py

Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Green
Write-Host "Frontend: http://localhost:5173"
Write-Host "Backend:  http://localhost:8000"
