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

// Application Insights connection string is the modern replacement for the
// classic instrumentation key. It encodes both the endpoint URL and the
// resource identity, which means the SDK works correctly in sovereign clouds
// and future endpoint migrations without code changes.
@description('Application Insights connection string for telemetry (pass empty string to disable)')
param appInsightsConnectionString string = ''

// ── CPU / memory sizing ───────────────────────────────────────────────────────
// Container Apps allocates CPU and memory in fixed pairs:
//   0.25 vCPU / 0.5 Gi  — fine for static content or very low traffic
//   0.5  vCPU / 1.0 Gi  — suitable for most API workloads (dev)
//   1.0  vCPU / 2.0 Gi  — production API with Playwright (image generation)
//   2.0  vCPU / 4.0 Gi  — high-traffic or CPU-intensive workloads
// Playwright (used by siege-api for image generation) is the most memory-
// hungry component, so the API gets a larger allocation.

@description('CPU cores for the API app (e.g. "0.5" for dev, "1.0" for prod)')
param apiCpu string = '0.5'

@description('Memory for the API app (e.g. "1Gi" for dev, "2Gi" for prod)')
param apiMemory string = '1Gi'

@description('Max replicas for the API app')
param apiMaxReplicas int = 3

@description('Minimum replicas for the API app (0 = scale to zero when idle)')
param apiMinReplicas int = 1

@description('Minimum replicas for the frontend app (0 = scale to zero when idle)')
param frontendMinReplicas int = 1

@description('CPU cores for the frontend app (e.g. "0.25")')
param frontendCpu string = '0.25'

@description('Memory for the frontend app (e.g. "0.5Gi")')
param frontendMemory string = '0.5Gi'

@description('CPU cores for the bot app (e.g. "0.25")')
param botCpu string = '0.25'

@description('Memory for the bot app (e.g. "0.5Gi")')
param botMemory string = '0.5Gi'

var apiAppName = '${appPrefix}-api-${environment}'
var frontendAppName = '${appPrefix}-frontend-${environment}'
var botAppName = '${appPrefix}-bot-${environment}'

// ── siege-api ────────────────────────────────────────────────────────────────

resource apiApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: apiAppName
  location: location
  tags: { project: appPrefix, environment: environment }
  identity: {
    // System-assigned managed identity lets the app authenticate to Key Vault
    // and ACR without storing any credentials — Azure handles the token lifecycle.
    type: 'SystemAssigned'
  }
  properties: {
    environmentId: containerAppsEnvironmentId
    configuration: {
      ingress: {
        // Internal-only ingress: the API is not directly reachable from the
        // internet. Traffic arrives via the frontend Nginx proxy (/api/* prefix).
        external: false
        targetPort: 8000
        transport: 'http'
        allowInsecure: true // Nginx proxies plain HTTP internally; without this Azure redirects to HTTPS (301), causing browsers to downgrade POST → GET → 405
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
          // Key Vault reference — value is fetched at runtime using the
          // app's managed identity. No secret value is stored in the Bicep
          // template or the Container Apps configuration plane.
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
            cpu: json(apiCpu)
            memory: apiMemory
          }
          env: concat(
            [
              { name: 'DATABASE_URL', secretRef: 'database-url' }
              { name: 'DISCORD_BOT_API_KEY', secretRef: 'discord-bot-api-key' }
              { name: 'DISCORD_BOT_API_URL', value: 'http://${botAppName}' }
              { name: 'DISCORD_GUILD_ID', value: discordGuildId }
              { name: 'ENVIRONMENT', value: environment }
            ],
            // Only inject the Application Insights connection string when one
            // has been provided — keeps dev deployments lightweight.
            empty(appInsightsConnectionString) ? [] : [
              { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
            ]
          )
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
        minReplicas: apiMinReplicas
        maxReplicas: apiMaxReplicas
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
        // Public ingress: the frontend is the only internet-facing entry point.
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
            cpu: json(frontendCpu)
            memory: frontendMemory
          }
          env: concat(
            [
              { name: 'VITE_API_URL', value: '' } // nginx proxies /api/* to siege-api internally
              { name: 'API_UPSTREAM', value: 'http://${apiAppName}' }
            ],
            empty(appInsightsConnectionString) ? [] : [
              { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
            ]
          )
        }
      ]
      scale: {
        minReplicas: frontendMinReplicas
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
        // Bot has no public ingress at all — it is only reachable from
        // siege-api within the same Container Apps environment via its
        // internal service name (http://siege-bot-<env>).
        external: false
        targetPort: 8001
        transport: 'http'
        allowInsecure: true // Same as API: internal HTTP calls from siege-api must not be redirected to HTTPS
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
            cpu: json(botCpu)
            memory: botMemory
          }
          env: concat(
            [
              { name: 'DISCORD_TOKEN', secretRef: 'discord-token' }
              { name: 'DATABASE_URL', secretRef: 'database-url' }
              { name: 'BOT_API_KEY', secretRef: 'bot-api-key' }
              { name: 'DISCORD_GUILD_ID', value: discordGuildId }
              { name: 'ENVIRONMENT', value: environment }
            ],
            empty(appInsightsConnectionString) ? [] : [
              { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
            ]
          )
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
        // Bot maintains a single replica — it holds a stateful Discord WebSocket
        // connection and multiple replicas would create duplicate event handlers.
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
