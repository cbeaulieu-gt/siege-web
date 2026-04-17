@description('Azure region for all resources')
param location string

@description('Environment name (dev, prod)')
param environment string

@description('Short prefix for resource naming')
param appPrefix string

@description('Log Analytics workspace customer ID')
param logAnalyticsCustomerId string

@description('Log Analytics workspace primary shared key')
@secure()
param logAnalyticsPrimaryKey string

@description('Resource ID of the user-assigned managed identity used to import certs from Key Vault. Leave empty to omit (identity block will be SystemAssigned).')
param certIdentityId string = ''

var envName = '${appPrefix}-cae-${environment}-${uniqueString(resourceGroup().id)}'

// The Container Apps environment needs an identity so it can authenticate to
// Key Vault and import the BYO certificate. We use a user-assigned identity
// rather than system-assigned so the role assignment can exist in the same
// Bicep deployment (system-assigned principal IDs are only known after the
// resource is first created).
//
// When certIdentityId is empty (dev with no cert), we fall back to a no-op
// identity block (None). This keeps the resource declaration unconditional and
// avoids the Bicep limitation around conditional identity blocks.

// The identity block on managedEnvironments was not present in the 2024-03-01 Bicep type
// definition. Using 2024-08-02-preview which includes the ManagedServiceIdentity property.
// This is the same preview version used for the certificates child resource.
resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-08-02-preview' = {
  name: envName
  location: location
  tags: {
    project: appPrefix
    environment: environment
  }
  identity: empty(certIdentityId)
    ? {
        type: 'None'
      }
    : {
        type: 'UserAssigned'
        userAssignedIdentities: {
          '${certIdentityId}': {}
        }
      }
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsCustomerId
        sharedKey: logAnalyticsPrimaryKey
      }
    }
  }
}

output environmentId string = containerAppsEnvironment.id
output environmentName string = containerAppsEnvironment.name
output defaultDomain string = containerAppsEnvironment.properties.defaultDomain
