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
  }
}

// ── Key Vault role assignments ────────────────────────────────────────────────
//
// Role assignments are delegated to a dedicated module so that the vault name
// and principal IDs arrive as plain string parameters rather than as module
// outputs. Bicep BCP120 forbids using module outputs as the `name` of a
// resource or as the target of an `existing` scope, because those values are
// only known at runtime. Inside kv-role-assignments.bicep the vault name is a
// regular parameter string, so `existing` resolves at compile time and
// `guid(keyVault.id, ...)` is valid.

module kvRoleAssignments 'modules/kv-role-assignments.bicep' = {
  name: 'kvRoleAssignments'
  params: {
    vaultName: keyVault.outputs.vaultName
    apiPrincipalId: containerApps.outputs.apiAppPrincipalId
    frontendPrincipalId: containerApps.outputs.frontendAppPrincipalId
    botPrincipalId: containerApps.outputs.botAppPrincipalId
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
