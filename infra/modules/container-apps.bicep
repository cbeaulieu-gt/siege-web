@description('Azure region for all resources')
param location string

@description('Environment name (dev, prod)')
param environment string

@description('Short prefix for resource naming')
param appPrefix string

@description('Container Apps Environment resource ID')
param containerAppsEnvironmentId string

@description('Container Apps Environment name — required for the managed certificate child resource')
param containerAppsEnvironmentName string

@description('Custom hostname to bind to the frontend (e.g. rslsiege.com). Leave empty to skip custom domain setup.')
param customDomainHostname string = ''

@description('Container registry login server (e.g. myregistry.azurecr.io)')
param acrLoginServer string

@description('Image tag to deploy')
param imageTag string = 'latest'

@description('Key Vault URI for secret references')
param keyVaultUri string

@description('Discord guild ID (non-secret)')
param discordGuildId string

@description('Discord OAuth2 redirect URI (non-secret; public URL visible in browser address bar)')
param discordRedirectUri string

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

@description('Public-facing URL injected as VITE_PUBLIC_URL into the frontend container (e.g. https://rslsiege.com). Leave empty to omit the variable.')
param publicUrl string = ''

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

// Whether a custom domain has been specified. Used to conditionally create
// the managed certificate and update the frontend ingress binding.
var hasCustomDomain = !empty(customDomainHostname)

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
        {
          name: 'session-secret'
          keyVaultUrl: '${keyVaultUri}secrets/session-secret'
          identity: 'system'
        }
        {
          name: 'discord-client-id'
          keyVaultUrl: '${keyVaultUri}secrets/discord-client-id'
          identity: 'system'
        }
        {
          name: 'discord-client-secret'
          keyVaultUrl: '${keyVaultUri}secrets/discord-client-secret'
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
              { name: 'SESSION_SECRET', secretRef: 'session-secret' }
              { name: 'DISCORD_CLIENT_ID', secretRef: 'discord-client-id' }
              { name: 'DISCORD_CLIENT_SECRET', secretRef: 'discord-client-secret' }
              { name: 'DISCORD_REDIRECT_URI', value: discordRedirectUri }
              { name: 'BOT_SERVICE_TOKEN', secretRef: 'discord-bot-api-key' }
              // When a custom domain is configured, allow CORS from that origin so
              // the browser can reach /api/* from the custom domain frontend.
              // Falls back to localhost:5173 for dev deployments without a custom domain.
              { name: 'ALLOWED_ORIGINS', value: !empty(customDomainHostname) ? 'https://${customDomainHostname}' : 'http://localhost:5173' }
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
        // Step 1 of 2 for custom domain binding.
        //
        // Azure managed certificates have a bootstrapping circular dependency:
        // the certificate resource needs the hostname pre-registered on the app
        // to perform domain validation, but the app's ingress needs the cert ID
        // to bind with SniEnabled. We break this cycle with a two-phase approach:
        //
        //   Phase 1 (this resource): register the hostname with bindingType
        //   'Disabled' so DNS ownership is verified and the cert can be issued.
        //
        //   Phase 2 (frontendAppCertBinding below): after the managedCertificate
        //   resource is provisioned, re-deploy the app with bindingType
        //   'SniEnabled' and the cert resource ID.
        //
        // On a fresh environment this completes in one `az deployment group create`
        // run. On subsequent runs the hostname is already registered so Phase 1 is
        // a no-op, and Phase 2 refreshes the binding if the cert was rotated.
        customDomains: hasCustomDomain
          ? [
              {
                name: customDomainHostname
                bindingType: 'Disabled'
              }
            ]
          : []
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
            ],
            empty(publicUrl) ? [] : [
              { name: 'VITE_PUBLIC_URL', value: publicUrl }
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

// ── Custom domain: Phase 2 ────────────────────────────────────────────────────
//
// Phase 1 (frontendApp above) registered the hostname with bindingType 'Disabled'
// so Azure could verify DNS ownership. Phase 2 provisions the managed TLS
// certificate and re-binds the frontend with 'SniEnabled'.
//
// The two resources below are only created when hasCustomDomain is true.
// On subsequent re-deployments both resources are idempotent: the cert is
// already issued and the binding is already SniEnabled — ARM simply confirms
// the desired state matches the live state and makes no changes.

// Reference to the managed environment so we can attach a child certificate
// resource to it. Using an `existing` reference avoids duplicating the
// environment definition here and keeps the dependency graph correct.
resource containerAppsEnv 'Microsoft.App/managedEnvironments@2024-03-01' existing = if (hasCustomDomain) {
  name: containerAppsEnvironmentName
}

// Managed certificate issued by Azure (Let's Encrypt / DigiCert) for the
// custom hostname. Azure performs CNAME validation: the hostname must already
// resolve to the Container App's FQDN via a CNAME record before this resource
// can be successfully created.
//
// NOTE for Cloudflare users: disable the proxy (grey cloud) on the CNAME record
// during first deploy so Azure can reach your domain for CNAME validation. Once
// the cert is issued and the binding is active you can re-enable the proxy.
resource managedCert 'Microsoft.App/managedEnvironments/managedCertificates@2024-03-01' = if (hasCustomDomain) {
  parent: containerAppsEnv
  name: take('${replace(customDomainHostname, '.', '-')}-cert', 60)
  location: location
  properties: {
    subjectName: customDomainHostname
    domainControlValidation: 'CNAME'
  }
  dependsOn: [
    frontendApp
  ]
}

// Second deployment of the frontend Container App that upgrades the custom
// domain binding from 'Disabled' (Phase 1) to 'SniEnabled' now that the
// managed certificate has been issued.
//
// ARM Container App updates are full PUTs, not PATCHes — all required properties
// must be included. This resource is an exact copy of frontendApp except for the
// customDomains bindingType and certificateId. Bicep's symbolic reference to
// frontendApp.properties.template copies the current template (containers,
// scale rules, etc.) so we don't duplicate container config here.
// MAINTENANCE WARNING: This resource duplicates the frontendApp configuration
// to update the custom domain binding from Disabled to SniEnabled. If you change
// the frontendApp ingress, registries, or secrets, you MUST mirror those changes
// here or the binding deployment will revert them.
resource frontendAppCertBinding 'Microsoft.App/containerApps@2024-03-01' = if (hasCustomDomain) {
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
        customDomains: [
          {
            name: customDomainHostname
            bindingType: 'SniEnabled'
            certificateId: managedCert.id
          }
        ]
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
    template: frontendApp.properties.template
  }
  // No explicit dependsOn needed: Bicep infers the dependency on managedCert
  // through the certificateId reference above.
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
