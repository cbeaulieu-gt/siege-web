@description('Azure region for all resources')
param location string

@description('Environment name (dev, prod)')
param environment string

@description('Short prefix for resource naming')
param appPrefix string

@description('SKU for the container registry (Basic, Standard, Premium)')
param acrSku string = 'Basic'

// ACR names must be alphanumeric only, 5-50 chars. Using a fixed, predictable
// name (e.g. siegeacrdev / siegeacrprod) so the GitHub Actions workflow can
// reference it without reading Bicep output at deploy time.
var sanitizedName = '${appPrefix}acr${environment}'

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: sanitizedName
  location: location
  tags: {
    project: appPrefix
    environment: environment
  }
  sku: {
    name: acrSku
  }
  properties: {
    adminUserEnabled: true
  }
}

output registryId string = registry.id
output registryName string = registry.name
output loginServer string = registry.properties.loginServer

@secure()
output acrUsername string = listCredentials(registry.id, '2023-07-01').username

@secure()
output acrPassword string = listCredentials(registry.id, '2023-07-01').passwords[0].value
