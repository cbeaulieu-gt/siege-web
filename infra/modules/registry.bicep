@description('Azure region for all resources')
param location string

@description('Environment name (dev, prod)')
param environment string

@description('Short prefix for resource naming')
param appPrefix string

@description('SKU for the container registry (Basic, Standard, Premium)')
param acrSku string = 'Basic'

@description('Override the generated ACR name (must be globally unique, 5-50 alphanumeric chars). Leave empty to use the default: appPrefix + "acr" + environment.')
param acrNameOverride string = ''

// ACR names must be alphanumeric only, 5-50 chars. Using a fixed, predictable
// name (e.g. siegeacrdev / siegeacrprod) so the GitHub Actions workflow can
// reference it without reading Bicep output at deploy time.
// acrNameOverride lets the dev environment supply a pre-checked globally-unique
// name (e.g. 'siegewebacr') without changing the default convention for prod.
var sanitizedName = empty(acrNameOverride) ? '${appPrefix}acr${environment}' : acrNameOverride

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
output acrUsername string = registry.listCredentials().username

@secure()
output acrPassword string = registry.listCredentials().passwords[0].value
