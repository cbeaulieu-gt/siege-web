param(
    [string]$ExcelPath   = 'E:\My Files\Games\Raid Shadow Legends\siege',
    [string]$Environment = 'dev'
)

$ErrorActionPreference = 'Stop'

if ($Environment -notin @('dev', 'prod')) {
    Write-Error "Invalid environment '$Environment'. Must be 'dev' or 'prod'."
    exit 1
}

$ResourceGroup = if ($Environment -eq 'dev') { 'siege-web-dev' } else { 'siege-rg' }

Write-Host "==> Excel import for environment: $Environment"
Write-Host "    Resource group: $ResourceGroup"
Write-Host "    Excel path: $ExcelPath"
Write-Host ""

# ── Validate Excel path ───────────────────────────────────────────────────────

Write-Host '==> Checking Excel path...'

if (-not (Test-Path $ExcelPath)) {
    Write-Error "Excel path not found: $ExcelPath"
    exit 1
}

$XlsmFiles = Get-ChildItem -Path $ExcelPath -Filter '*.xlsm' -File
$FileCount  = $XlsmFiles.Count

if ($FileCount -eq 0) {
    Write-Error "No .xlsm files found in: $ExcelPath`nEnsure the siege export files are present before running this script."
    exit 1
}

Write-Host "    Found $FileCount .xlsm file(s)."
Write-Host ""
Write-Host "    NOTE: Filenames must match the pattern clan_siege_DD_MM_YYYY.xlsm for"
Write-Host "    the siege date to be parsed correctly. Files that do not match this"
Write-Host "    pattern will be imported without a date."
Write-Host ""

# ── Install script dependencies ───────────────────────────────────────────────

Write-Host '==> Installing script dependencies from scripts/requirements.txt...'
Write-Host '    pip output below may be verbose -- this is expected.'
Write-Host ""

pip install -r scripts/requirements.txt

if ($LASTEXITCODE -ne 0) {
    Write-Error 'pip install failed. Check the output above for details.'
    exit 1
}

Write-Host ""

# ── Look up database URL from Azure Key Vault ─────────────────────────────────

Write-Host "==> Looking up Key Vault name in resource group $ResourceGroup..."

$VaultName = az keyvault list -g $ResourceGroup --query "[0].name" -o tsv 2>&1

if ($LASTEXITCODE -ne 0 -or -not $VaultName) {
    Write-Error "Could not find a Key Vault in resource group '$ResourceGroup'.`nEnsure the Bicep deployment has run and you are logged in to the correct Azure subscription."
    exit 1
}

Write-Host "    Vault: $VaultName"
Write-Host ""

Write-Host '==> Fetching database URL from Key Vault...'

$DbUrl = az keyvault secret show --vault-name $VaultName --name database-url --query value -o tsv 2>&1

if ($LASTEXITCODE -ne 0 -or -not $DbUrl) {
    Write-Error "Could not retrieve secret 'database-url' from vault '$VaultName'.`nEnsure the Bicep deployment has run and you are logged in to the correct Azure subscription."
    exit 1
}

Write-Host "    Secret retrieved."
Write-Host ""

# ── Add local IP to PostgreSQL firewall ───────────────────────────────────────

Write-Host '==> Looking up PostgreSQL server name...'

$PgServer = az postgres flexible-server list -g $ResourceGroup --query "[0].name" -o tsv 2>&1

if ($LASTEXITCODE -ne 0 -or -not $PgServer) {
    Write-Error "Could not find a PostgreSQL server in resource group '$ResourceGroup'."
    exit 1
}

Write-Host "    Server: $PgServer"

Write-Host '==> Detecting your public IP address...'
$MyIp = (Invoke-RestMethod -Uri 'https://api.ipify.org').Trim()
Write-Host "    IP: $MyIp"

$FirewallRuleName = "local-import-$(Get-Date -Format 'yyyyMMddHHmmss')"

Write-Host "==> Adding temporary firewall rule '$FirewallRuleName'..."

az postgres flexible-server firewall-rule create `
    --resource-group $ResourceGroup `
    --name $PgServer `
    --rule-name $FirewallRuleName `
    --start-ip-address $MyIp `
    --end-ip-address $MyIp

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to add firewall rule. Check the output above."
    exit 1
}

Write-Host "    Firewall rule added."
Write-Host ""

# ── Run the import script ─────────────────────────────────────────────────────

Write-Host '==> Running Excel import...'
Write-Host ""

try {
    python scripts/import_excel.py "$ExcelPath" --database-url $DbUrl

    if ($LASTEXITCODE -ne 0) {
        Write-Error 'Excel import failed. Check the output above for details.'
        exit 1
    }
} finally {
    Write-Host ""
    Write-Host "==> Removing temporary firewall rule '$FirewallRuleName'..."
    az postgres flexible-server firewall-rule delete `
        --resource-group $ResourceGroup `
        --name $PgServer `
        --rule-name $FirewallRuleName `
        --yes 2>&1 | Out-Null
    Write-Host "    Firewall rule removed."
}

Write-Host ""
Write-Host "==> Import complete. Processed $FileCount .xlsm file(s) from: $ExcelPath"
