@description('Azure region for all resources')
param location string

@description('Environment name (dev, prod)')
param environment string

@description('Short prefix for resource naming')
param appPrefix string

@description('Full database connection URL (postgresql+asyncpg://user:pass@host/db)')
@secure()
param databaseUrl string

@description('Discord bot token')
@secure()
param discordToken string

@description('Discord guild (server) ID')
param discordGuildId string

@description('API key used by backend to call the bot HTTP API')
@secure()
param discordBotApiKey string

@description('API key the bot HTTP API validates on inbound requests')
@secure()
param botApiKey string

@description('Object IDs of the Container App managed identities that need secret access')
param containerAppPrincipalIds array = []

var vaultName = '${appPrefix}-kv-${environment}-${take(uniqueString(resourceGroup().id), 6)}'

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: vaultName
  location: location
  tags: {
    project: appPrefix
    environment: environment
  }
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Enabled'
  }
}

resource secretDatabaseUrl 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'database-url'
  properties: { value: databaseUrl }
}

resource secretDiscordToken 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'discord-token'
  properties: { value: discordToken }
}

resource secretDiscordGuildId 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'discord-guild-id'
  properties: { value: discordGuildId }
}

resource secretDiscordBotApiKey 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'discord-bot-api-key'
  properties: { value: discordBotApiKey }
}

resource secretBotApiKey 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'bot-api-key'
  properties: { value: botApiKey }
}

// Grant each Container App managed identity the "Key Vault Secrets User" role
resource kvSecretsUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for (principalId, i) in containerAppPrincipalIds: {
    name: guid(keyVault.id, principalId, '4633458b-17de-408a-b874-0445c86b69e6')
    scope: keyVault
    properties: {
      roleDefinitionId: subscriptionResourceId(
        'Microsoft.Authorization/roleDefinitions',
        '4633458b-17de-408a-b874-0445c86b69e6' // Key Vault Secrets User
      )
      principalId: principalId
      principalType: 'ServicePrincipal'
    }
  }
]

output vaultId string = keyVault.id
output vaultName string = keyVault.name
output vaultUri string = keyVault.properties.vaultUri
output secretDatabaseUrlUri string = secretDatabaseUrl.properties.secretUri
output secretDiscordTokenUri string = secretDiscordToken.properties.secretUri
output secretDiscordBotApiKeyUri string = secretDiscordBotApiKey.properties.secretUri
output secretBotApiKeyUri string = secretBotApiKey.properties.secretUri
