$ErrorActionPreference = 'Stop'

Write-Host '==> Looking up ACR login server in resource group siege-rg...'
$Registry = az acr list --resource-group siege-rg --query "[0].loginServer" -o tsv

if (-not $Registry) {
    Write-Error 'No ACR found in resource group siege-rg. Ensure the Bicep deployment has completed and you are logged in to the correct Azure subscription.'
    exit 1
}

Write-Host "    Registry: $Registry"

$Images = @(
    @{ Name = 'siege-api';      Context = './backend'  },
    @{ Name = 'siege-frontend'; Context = './frontend' },
    @{ Name = 'siege-bot';      Context = './bot'      }
)

Write-Host '==> Logging in to Azure Container Registry...'
az acr login --name $Registry

foreach ($Image in $Images) {
    $Tag = "$Registry/$($Image.Name):latest"

    Write-Host ""
    Write-Host "==> Building $Tag from $($Image.Context)..."
    docker build -t $Tag $Image.Context

    Write-Host "==> Pushing $Tag..."
    docker push $Tag
}

Write-Host ""
Write-Host "==> All images pushed successfully."
Write-Host "    Re-run your Bicep deployment to pick up the new images:"
Write-Host "    az deployment group create --resource-group <rg> --template-file infra/main.bicep --parameters @infra/main.parameters.json"
