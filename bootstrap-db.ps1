param(
    [string]$Environment = 'dev'
)

$ErrorActionPreference = 'Stop'

$ResourceGroup = 'siege-rg'
$ApiApp        = "siege-api-$Environment"
$FrontendApp   = "siege-frontend-$Environment"

Write-Host "==> Bootstrapping database for environment: $Environment"
Write-Host "    Container app : $ApiApp"
Write-Host "    Resource group: $ResourceGroup"
Write-Host ""

# ── Check the API container app exists and is running ────────────────────────

Write-Host '==> Checking API container app status...'

$AppJson = az containerapp show `
    --name $ApiApp `
    --resource-group $ResourceGroup `
    --query '{state:properties.runningStatus}' `
    -o json 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Error "Container app '$ApiApp' not found in resource group '$ResourceGroup'. Verify the Bicep deployment has completed and you are logged in to the correct Azure subscription."
    exit 1
}

$App   = $AppJson | ConvertFrom-Json
$State = $App.state

if ($State -ne 'Running') {
    Write-Error "Container app '$ApiApp' is not running (current state: $State). Check the app health in the Azure Portal before running this script."
    exit 1
}

Write-Host "    Status: $State"
Write-Host ""

# ── Run Alembic migrations ────────────────────────────────────────────────────

Write-Host '==> Running Alembic migrations (alembic upgrade head)...'
Write-Host '    This is safe to run multiple times — Alembic skips already-applied revisions.'
Write-Host ""

az containerapp exec `
    --name $ApiApp `
    --resource-group $ResourceGroup `
    --command "alembic upgrade head"

if ($LASTEXITCODE -ne 0) {
    Write-Error 'Alembic migration failed. Check the output above for details.'
    exit 1
}

Write-Host ""

# ── Seed the database ─────────────────────────────────────────────────────────

Write-Host '==> Seeding database (python seed.py)...'
Write-Host '    seed.py is idempotent and safe to re-run, but may print warnings if reference data already exists — that is expected.'
Write-Host ""

az containerapp exec `
    --name $ApiApp `
    --resource-group $ResourceGroup `
    --command "python seed.py"

if ($LASTEXITCODE -ne 0) {
    Write-Error 'Database seed failed. Check the output above for details.'
    exit 1
}

Write-Host ""

# ── Look up frontend URL ──────────────────────────────────────────────────────

Write-Host '==> Looking up frontend URL...'

$FrontendJson = az containerapp show `
    --name $FrontendApp `
    --resource-group $ResourceGroup `
    --query 'properties.configuration.ingress.fqdn' `
    -o tsv 2>&1

if ($LASTEXITCODE -ne 0 -or -not $FrontendJson) {
    Write-Host "    (Could not resolve frontend URL for '$FrontendApp' - deployment may not include a frontend for this environment.)"
} else {
    $FrontendUrl = "https://$FrontendJson"
    Write-Host ""
    Write-Host "==> Database bootstrap complete."
    Write-Host "    Frontend: $FrontendUrl"
    exit 0
}

Write-Host ""
Write-Host '==> Database bootstrap complete.'
