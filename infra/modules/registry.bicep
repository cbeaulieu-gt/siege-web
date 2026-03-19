@description('Azure region for all resources')
param location string

@description('Environment name (dev, prod)')
param environment string

@description('Short prefix for resource naming')
param appPrefix string

@description('SKU for the container registry (Basic, Standard, Premium)')
param acrSku string = 'Basic'

var registryName = '${appPrefix}registry${environment}${uniqueString(resourceGroup().id)}'
// ACR names must be alphanumeric only, 5-50 chars
var sanitizedName = take(replace(replace(registryName, '-', ''), '_', ''), 50)

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
