@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Environment name: dev or prod')
@allowed(['dev', 'prod'])
param environment string = 'dev'

@description('Short prefix used in resource names')
param appPrefix string = 'siege'

@description('Container Registry SKU (Basic for dev, Standard for prod)')
param acrSku string = 'Basic'

@description('Image tag to deploy')
param imageTag string = 'latest'

@description('PostgreSQL administrator username')
param postgresAdminUser string = 'siegeadmin'

@description('PostgreSQL administrator password')
@secure()
param postgresAdminPassword string

@description('Discord bot token')
@secure()
param discordToken string

@description('Discord guild (server) ID')
param discordGuildId string

@description('API key used by backend to call the bot HTTP API')
@secure()
param discordBotApiKey string

@description('API key the bot validates on inbound HTTP requests')
@secure()
param botApiKey string

@description('Enable geo-redundant PostgreSQL backup (set true for prod)')
param postgresGeoRedundantBackup bool = false

// ── Modules ──────────────────────────────────────────────────────────────────

module logAnalytics 'modules/log-analytics.bicep' = {
  name: 'logAnalytics'
  params: {
    location: location
    environment: environment
    appPrefix: appPrefix
  }
}

module registry 'modules/registry.bicep' = {
  name: 'registry'
  params: {
    location: location
    environment: environment
    appPrefix: appPrefix
    acrSku: acrSku
  }
}

module postgres 'modules/postgres.bicep' = {
  name: 'postgres'
  params: {
    location: location
    environment: environment
    appPrefix: appPrefix
    adminUsername: postgresAdminUser
    adminPassword: postgresAdminPassword
    geoRedundantBackup: postgresGeoRedundantBackup
  }
}

module keyVault 'modules/keyvault.bicep' = {
  name: 'keyVault'
  params: {
    location: location
    environment: environment
    appPrefix: appPrefix
    databaseUrl: 'postgresql+asyncpg://${postgresAdminUser}:${postgresAdminPassword}@${postgres.outputs.serverFqdn}/siege'
    discordToken: discordToken
    discordGuildId: discordGuildId
    discordBotApiKey: discordBotApiKey
    botApiKey: botApiKey
  }
}

module containerEnv 'modules/container-env.bicep' = {
  name: 'containerEnv'
  params: {
    location: location
    environment: environment
    appPrefix: appPrefix
    logAnalyticsCustomerId: logAnalytics.outputs.customerId
    logAnalyticsPrimaryKey: logAnalytics.outputs.primarySharedKey
  }
}

module containerApps 'modules/container-apps.bicep' = {
  name: 'containerApps'
  params: {
    location: location
    environment: environment
    appPrefix: appPrefix
    containerAppsEnvironmentId: containerEnv.outputs.environmentId
    acrLoginServer: registry.outputs.loginServer
    imageTag: imageTag
    keyVaultUri: keyVault.outputs.vaultUri
    discordGuildId: discordGuildId
    acrUsername: registry.outputs.acrUsername
    acrPassword: registry.outputs.acrPassword
    environmentDefaultDomain: containerEnv.outputs.defaultDomain
  }
}

// ── Key Vault role assignments ────────────────────────────────────────────────
//
// We create these in main.bicep AFTER containerApps runs so that the managed
// identity principal IDs are already known. A module-scoped role assignment
// loop inside keyvault.bicep can't reference outputs from a sibling module, so
// this is the correct pattern: use `existing` to get a handle on the vault,
// then assign the built-in "Key Vault Secrets User" role
// (4633458b-17de-408a-b874-0445c86b69e6) to each Container App's
// system-assigned managed identity.

resource existingKeyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVault.outputs.vaultName
}

resource kvRoleApi 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.outputs.vaultId, containerApps.outputs.apiAppPrincipalId, '4633458b-17de-408a-b874-0445c86b69e6')
  scope: existingKeyVault
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '4633458b-17de-408a-b874-0445c86b69e6' // Key Vault Secrets User
    )
    principalId: containerApps.outputs.apiAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource kvRoleFrontend 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.outputs.vaultId, containerApps.outputs.frontendAppPrincipalId, '4633458b-17de-408a-b874-0445c86b69e6')
  scope: existingKeyVault
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '4633458b-17de-408a-b874-0445c86b69e6' // Key Vault Secrets User
    )
    principalId: containerApps.outputs.frontendAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource kvRoleBot 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.outputs.vaultId, containerApps.outputs.botAppPrincipalId, '4633458b-17de-408a-b874-0445c86b69e6')
  scope: existingKeyVault
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '4633458b-17de-408a-b874-0445c86b69e6' // Key Vault Secrets User
    )
    principalId: containerApps.outputs.botAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ── Outputs ──────────────────────────────────────────────────────────────────

output registryLoginServer string = registry.outputs.loginServer
output postgresServerFqdn string = postgres.outputs.serverFqdn
output keyVaultName string = keyVault.outputs.vaultName
output containerAppsEnvironmentName string = containerEnv.outputs.environmentName
output frontendFqdn string = containerApps.outputs.frontendAppFqdn
output apiAppName string = containerApps.outputs.apiAppName
output botAppName string = containerApps.outputs.botAppName
