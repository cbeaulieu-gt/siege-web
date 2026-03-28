# Recovery script for when the Excel import ran against an unseeded database.
# Runs migrations + seed, wipes any partial siege records, then re-runs the import.
#
# Usage:
#   .\bootstrap-reimport.ps1 -Environment prod
#   .\bootstrap-reimport.ps1 -Environment dev -ExcelPath "D:\siege\files"

param(
    [Parameter(Mandatory)]
    [ValidateSet('dev', 'prod')]
    [string]$Environment,

    [string]$ExcelPath = 'E:\My Files\Games\Raid Shadow Legends\siege'
)

$ErrorActionPreference = 'Stop'

$ResourceGroup = if ($Environment -eq 'dev') { 'siege-web-dev' } else { 'siege-web-prod' }
$ApiApp        = "siege-web-api-$Environment"

Write-Host "==> Reimport for environment: $Environment"
Write-Host "    Resource group: $ResourceGroup"
Write-Host "    Container app : $ApiApp"
Write-Host "    Excel path    : $ExcelPath"
Write-Host ""

# ── Step 1: DB bootstrap (migrations + seed) ──────────────────────────────────

Write-Host '==> Step 1/3: Running database bootstrap (migrations + seed)...'
Write-Host ""

& "$PSScriptRoot\bootstrap-db.ps1" -Environment $Environment

if ($LASTEXITCODE -ne 0) {
    Write-Error 'Database bootstrap failed.'
    exit 1
}

Write-Host ""

# ── Step 2: Wipe partial siege data ──────────────────────────────────────────

Write-Host '==> Step 2/3: Wiping partial siege data...'
Write-Host "    The previous import ran against an unseeded database. Wiping partial"
Write-Host "    siege records so the re-import starts from a clean state."
Write-Host ""

$WipeScript = @'
import asyncio
from app.db.session import AsyncSessionLocal
from app.models import Siege
from sqlalchemy import delete

async def wipe():
    async with AsyncSessionLocal() as s:
        result = await s.execute(delete(Siege))
        await s.commit()
        print(f'Sieges cleared ({result.rowcount} row(s) deleted).')

asyncio.run(wipe())
'@

$B64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($WipeScript))

az containerapp exec `
    --name $ApiApp `
    --resource-group $ResourceGroup `
    --command "bash -c 'echo $B64 | base64 -d > /tmp/wipe.py && python /tmp/wipe.py'"

if ($LASTEXITCODE -ne 0) {
    Write-Error 'Wipe failed. Check the output above for details.'
    exit 1
}

Write-Host ""

# ── Step 3: Re-run Excel import ───────────────────────────────────────────────

Write-Host '==> Step 3/3: Re-running Excel import...'
Write-Host ""

& "$PSScriptRoot\bootstrap-excel-import.ps1" -ExcelPath $ExcelPath -Environment $Environment

if ($LASTEXITCODE -ne 0) {
    Write-Error 'Excel import failed. Check the output above for details.'
    exit 1
}

Write-Host ""
Write-Host '==> Reimport complete.'
