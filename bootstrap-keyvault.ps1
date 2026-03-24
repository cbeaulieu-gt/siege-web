param(
    [Parameter(Mandatory)][string]$ResourceGroup,
    [Parameter(Mandatory)][string]$VaultName,
    [string]$Environment = 'dev'
)

$ErrorActionPreference = 'Stop'

$RoleDefinitionName = 'Key Vault Secrets User'
$Apps = @("siege-web-api-$Environment", "siege-web-bot-$Environment")

Write-Host "==> Looking up Key Vault scope for '$VaultName'..."
$VaultId = az keyvault show --name $VaultName --resource-group $ResourceGroup --query "id" -o tsv

if (-not $VaultId) {
    Write-Error "Key Vault '$VaultName' not found in resource group '$ResourceGroup'."
    exit 1
}

Write-Host "    Vault ID: $VaultId"

foreach ($App in $Apps) {
    Write-Host ""
    Write-Host "==> Looking up managed identity for Container App '$App'..."
    $PrincipalId = az containerapp show --name $App --resource-group $ResourceGroup --query "identity.principalId" -o tsv

    if (-not $PrincipalId) {
        Write-Error "Could not retrieve principal ID for Container App '$App'. Ensure the app exists and has a system-assigned managed identity."
        exit 1
    }

    Write-Host "    Principal ID: $PrincipalId"

    Write-Host "==> Assigning '$RoleDefinitionName' to '$App' on Key Vault..."
    az role assignment create `
        --role $RoleDefinitionName `
        --assignee-object-id $PrincipalId `
        --assignee-principal-type ServicePrincipal `
        --scope $VaultId
}

Write-Host ""
Write-Host "==> Role assignments complete."
Write-Host "    Re-run your Bicep deployment to apply Key Vault references to the Container Apps:"
Write-Host "    az deployment group create --resource-group $ResourceGroup --template-file infra/main.bicep --parameters infra/main.$Environment.bicepparam"
