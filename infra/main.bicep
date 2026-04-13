@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Environment name: dev or prod')
@allowed(['dev', 'prod'])
param environment string = 'dev'

@description('Short prefix used in resource names')
param appPrefix string = 'siege'

@description('Container Registry SKU (Basic for dev, Standard for prod)')
param acrSku string = 'Basic'

@description('Override the generated ACR name. Leave empty to use the default convention (appPrefix + "acr" + environment).')
param acrNameOverride string = ''

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

@description('Secret key for signing JWT session cookies')
@secure()
param sessionSecret string

@description('Discord OAuth2 application client ID')
@secure()
param discordClientId string

@description('Discord OAuth2 application client secret')
@secure()
param discordClientSecret string

@description('Discord OAuth2 redirect URI (full callback URL)')
param discordRedirectUri string

@description('Enable geo-redundant PostgreSQL backup (set true for prod)')
param postgresGeoRedundantBackup bool = false

// ── PostgreSQL sizing ─────────────────────────────────────────────────────────
// Dev default: Burstable B1ms — cheap shared vCores, adequate for testing.
// Prod recommendation: GeneralPurpose Standard_D2ds_v5 — dedicated 2 vCores,
// required for zone-redundant HA and consistent query performance.

@description('PostgreSQL SKU name (Standard_B1ms for dev, Standard_D2ds_v5 for prod)')
param postgresSku string = 'Standard_B1ms'

@description('PostgreSQL SKU tier (Burstable | GeneralPurpose | MemoryOptimized)')
@allowed(['Burstable', 'GeneralPurpose', 'MemoryOptimized'])
param postgresSkuTier string = 'Burstable'

@description('PostgreSQL storage size in GB')
param postgresStorageGB int = 32

@description('PostgreSQL backup retention in days (7–35)')
@minValue(7)
@maxValue(35)
param postgresBackupRetentionDays int = 7

@description('PostgreSQL high availability mode (Disabled | SameZone | ZoneRedundant)')
@allowed(['Disabled', 'SameZone', 'ZoneRedundant'])
param postgresHighAvailability string = 'Disabled'

// ── Key Vault ─────────────────────────────────────────────────────────────────

@description('Key Vault soft-delete retention in days (7 for dev, 90 for prod)')
@minValue(7)
@maxValue(90)
param kvSoftDeleteRetentionDays int = 7

// ── Log Analytics ─────────────────────────────────────────────────────────────

@description('Log Analytics retention in days (30 for dev, 90 for prod)')
param logRetentionDays int = 30

// ── Container App sizing ──────────────────────────────────────────────────────
// These parameters let each environment pick appropriate CPU/memory without
// forking the module. Prod uses larger allocations because the API runs
// Playwright (headless Chromium) for image generation.

@description('API Container App CPU (e.g. "0.5" dev, "1.0" prod)')
param apiCpu string = '0.5'

@description('API Container App memory (e.g. "1Gi" dev, "2Gi" prod)')
param apiMemory string = '1Gi'

@description('API Container App max replicas')
param apiMaxReplicas int = 3

@description('Frontend Container App CPU')
param frontendCpu string = '0.25'

@description('Frontend Container App memory')
param frontendMemory string = '0.5Gi'

@description('Bot Container App CPU')
param botCpu string = '0.25'

@description('Bot Container App memory')
param botMemory string = '0.5Gi'

@description('Minimum replicas for the API app (0 = scale to zero when idle)')
param apiMinReplicas int = 1

@description('Minimum replicas for the frontend app (0 = scale to zero when idle)')
param frontendMinReplicas int = 1

@description('Public-facing URL for canonical/og tags (e.g. https://rslsiege.com). Leave empty for dev.')
param publicUrl string = ''

// ── Modules ──────────────────────────────────────────────────────────────────

module logAnalytics 'modules/log-analytics.bicep' = {
  name: 'logAnalytics'
  params: {
    location: location
    environment: environment
    appPrefix: appPrefix
    retentionInDays: logRetentionDays
  }
}

module registry 'modules/registry.bicep' = {
  name: 'registry'
  params: {
    location: location
    environment: environment
    appPrefix: appPrefix
    acrSku: acrSku
    acrNameOverride: acrNameOverride
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
    postgresSku: postgresSku
    postgresSkuTier: postgresSkuTier
    storageSizeGB: postgresStorageGB
    backupRetentionDays: postgresBackupRetentionDays
    highAvailabilityMode: postgresHighAvailability
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
    sessionSecret: sessionSecret
    discordClientId: discordClientId
    discordClientSecret: discordClientSecret
    softDeleteRetentionDays: kvSoftDeleteRetentionDays
  }
}

// Application Insights — workspace-based mode links telemetry to the same
// Log Analytics workspace used for container logs, giving one unified query
// surface. This module is always deployed; the connection string is threaded
// into all three Container Apps as APPLICATIONINSIGHTS_CONNECTION_STRING.
module appInsights 'modules/app-insights.bicep' = {
  name: 'appInsights'
  params: {
    location: location
    environment: environment
    appPrefix: appPrefix
    logAnalyticsWorkspaceId: logAnalytics.outputs.resourceId
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
    discordRedirectUri: discordRedirectUri
    acrUsername: registry.outputs.acrUsername
    acrPassword: registry.outputs.acrPassword
    appInsightsConnectionString: appInsights.outputs.connectionString
    apiCpu: apiCpu
    apiMemory: apiMemory
    apiMaxReplicas: apiMaxReplicas
    frontendCpu: frontendCpu
    frontendMemory: frontendMemory
    botCpu: botCpu
    botMemory: botMemory
    apiMinReplicas: apiMinReplicas
    frontendMinReplicas: frontendMinReplicas
    publicUrl: publicUrl
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
output appInsightsName string = appInsights.outputs.appInsightsName
output containerAppsEnvironmentName string = containerEnv.outputs.environmentName
output frontendFqdn string = containerApps.outputs.frontendAppFqdn
output apiAppName string = containerApps.outputs.apiAppName
output botAppName string = containerApps.outputs.botAppName
