@description('Azure region for all resources')
param location string

@description('Environment name (dev, prod)')
param environment string

@description('Short prefix for resource naming')
param appPrefix string

@description('Container Apps Environment resource ID')
param containerAppsEnvironmentId string

@description('Container registry login server (e.g. myregistry.azurecr.io)')
param acrLoginServer string

@description('Image tag to deploy')
param imageTag string = 'latest'

@description('Key Vault URI for secret references')
param keyVaultUri string

@description('Discord guild ID (non-secret)')
param discordGuildId string

@description('ACR admin username for image pull authentication')
param acrUsername string

@description('ACR admin password for image pull authentication')
@secure()
param acrPassword string

@description('Default domain of the Container Apps Environment (e.g. mangotree-7248c553.australiaeast.azurecontainerapps.io)')
param environmentDefaultDomain string

var apiAppName = '${appPrefix}-api-${environment}'
var frontendAppName = '${appPrefix}-frontend-${environment}'
var botAppName = '${appPrefix}-bot-${environment}'

// ── siege-api ────────────────────────────────────────────────────────────────

resource apiApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: apiAppName
  location: location
  tags: { project: appPrefix, environment: environment }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    environmentId: containerAppsEnvironmentId
    configuration: {
      ingress: {
        external: false
        targetPort: 8000
        transport: 'http'
      }
      registries: [
        {
          server: acrLoginServer
          username: acrUsername
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        {
          name: 'acr-password'
          value: acrPassword
        }
        {
          name: 'database-url'
          keyVaultUrl: '${keyVaultUri}secrets/database-url'
          identity: 'system'
        }
        {
          name: 'discord-bot-api-key'
          keyVaultUrl: '${keyVaultUri}secrets/discord-bot-api-key'
          identity: 'system'
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'siege-api'
          image: '${acrLoginServer}/siege-api:${imageTag}'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'DATABASE_URL', secretRef: 'database-url' }
            { name: 'DISCORD_BOT_API_KEY', secretRef: 'discord-bot-api-key' }
            { name: 'DISCORD_BOT_API_URL', value: 'https://${botAppName}.internal.${environmentDefaultDomain}' }
            { name: 'DISCORD_GUILD_ID', value: discordGuildId }
            { name: 'ENVIRONMENT', value: environment }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/api/health'
                port: 8000
              }
              initialDelaySeconds: 15
              periodSeconds: 30
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
      }
    }
  }
}

// ── siege-frontend ────────────────────────────────────────────────────────────

resource frontendApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: frontendAppName
  location: location
  tags: { project: appPrefix, environment: environment }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    environmentId: containerAppsEnvironmentId
    configuration: {
      ingress: {
        external: true
        targetPort: 80
        transport: 'http'
      }
      registries: [
        {
          server: acrLoginServer
          username: acrUsername
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        {
          name: 'acr-password'
          value: acrPassword
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'siege-frontend'
          image: '${acrLoginServer}/siege-frontend:${imageTag}'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            { name: 'VITE_API_URL', value: '' } // nginx proxies /api/* to siege-api internally
            { name: 'API_UPSTREAM', value: 'https://${apiAppName}.internal.${environmentDefaultDomain}' }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 2
      }
    }
  }
}

// ── siege-bot ─────────────────────────────────────────────────────────────────

resource botApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: botAppName
  location: location
  tags: { project: appPrefix, environment: environment }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    environmentId: containerAppsEnvironmentId
    configuration: {
      ingress: {
        external: false
        targetPort: 8001
        transport: 'http'
      }
      registries: [
        {
          server: acrLoginServer
          username: acrUsername
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        {
          name: 'acr-password'
          value: acrPassword
        }
        {
          name: 'discord-token'
          keyVaultUrl: '${keyVaultUri}secrets/discord-token'
          identity: 'system'
        }
        {
          name: 'database-url'
          keyVaultUrl: '${keyVaultUri}secrets/database-url'
          identity: 'system'
        }
        {
          name: 'bot-api-key'
          keyVaultUrl: '${keyVaultUri}secrets/bot-api-key'
          identity: 'system'
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'siege-bot'
          image: '${acrLoginServer}/siege-bot:${imageTag}'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            { name: 'DISCORD_TOKEN', secretRef: 'discord-token' }
            { name: 'DATABASE_URL', secretRef: 'database-url' }
            { name: 'BOT_API_KEY', secretRef: 'bot-api-key' }
            { name: 'DISCORD_GUILD_ID', value: discordGuildId }
            { name: 'ENVIRONMENT', value: environment }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/api/health'
                port: 8001
              }
              initialDelaySeconds: 20
              periodSeconds: 30
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

output apiAppName string = apiApp.name
output apiAppPrincipalId string = apiApp.identity.principalId
output frontendAppName string = frontendApp.name
output frontendAppFqdn string = frontendApp.properties.configuration.ingress.fqdn
output frontendAppPrincipalId string = frontendApp.identity.principalId
output botAppName string = botApp.name
output botAppPrincipalId string = botApp.identity.principalId
