using 'main.bicep'

// ── Production parameter file ─────────────────────────────────────────────────
//
// Deploy command:
//
//   az deployment group create \
//     --resource-group siege-rg-prod \
//     --template-file infra/main.bicep \
//     --parameters infra/main.prod.bicepparam \
//     --parameters postgresAdminPassword="$PG_ADMIN_PASSWORD" \
//     --parameters discordToken="$DISCORD_TOKEN" \
//     --parameters discordBotApiKey="$DISCORD_BOT_API_KEY" \
//     --parameters botApiKey="$BOT_API_KEY" \
//     --parameters discordGuildId="$DISCORD_GUILD_ID" \
//     --parameters sessionSecret="$SESSION_SECRET" \
//     --parameters discordClientId="$DISCORD_CLIENT_ID" \
//     --parameters discordClientSecret="$DISCORD_CLIENT_SECRET"
//     --parameters discordRedirectUri="https://prod.example.com/api/auth/callback"  # plain config, not a secret
//
// NEVER commit real secrets here. All @secure() params must be supplied at
// deploy time via environment variables or a CI/CD secret store.
//
// Resource group convention:
//   dev  → siege-rg-dev
//   prod → siege-rg-prod
// ─────────────────────────────────────────────────────────────────────────────

param environment = 'prod'
param appPrefix = 'siege-web'
param location = 'westus'

// ── Container Registry ────────────────────────────────────────────────────────
// Standard SKU enables geo-replication, content trust, and higher throughput
// pull limits compared to Basic. Required for production workloads.
param acrSku = 'Standard'

// Prod ACR is already deployed as siegeacrprod — override keeps the existing
// registry rather than creating a new hyphenated name.
param acrNameOverride = 'siegeacrprod'

param imageTag = 'latest'

// ── PostgreSQL ────────────────────────────────────────────────────────────────
// Burstable B1ms: 1 vCore (burstable), 2 GiB RAM — sufficient for a clan-sized
// user base (<100 concurrent users). Upgrade to D2ds_v5 (GeneralPurpose) if
// query latency becomes an issue under real load. HA can be re-enabled at any
// time without data loss.
param postgresSku = 'Standard_B1ms'
param postgresSkuTier = 'Burstable'
param postgresStorageGB = 32
param postgresBackupRetentionDays = 7   // increase to 35 for maximum retention
param postgresGeoRedundantBackup = false
param postgresHighAvailability = 'Disabled'

param postgresAdminUser = 'siegeadmin'
// Supply at deploy time: --parameters postgresAdminPassword="$PG_ADMIN_PASSWORD"
param postgresAdminPassword = ''

// ── Discord secrets ───────────────────────────────────────────────────────────
param discordGuildId = '' // Your Discord server ID (non-secret; ok to fill in)
// Supply at deploy time:
param discordToken = ''
param discordBotApiKey = ''
param botApiKey = ''

// ── OAuth2 secrets ────────────────────────────────────────────────────────────
// Supply at deploy time:
param sessionSecret = ''
param discordClientId = ''
param discordClientSecret = ''

// ── OAuth2 config (non-secret) ────────────────────────────────────────────────
// The redirect URI is a public URL (visible in the browser address bar during
// the OAuth flow). It is config, not a secret — supply inline or via vars.*.
param discordRedirectUri = 'https://siegeweb-prod.example.com/api/auth/callback'

// ── Key Vault ─────────────────────────────────────────────────────────────────
// 90-day soft-delete retention gives the maximum recovery window for secrets
// accidentally deleted or overwritten. The dev value of 7 days enables fast
// teardown of test environments but is not appropriate for production.
param kvSoftDeleteRetentionDays = 90

// ── Log Analytics ─────────────────────────────────────────────────────────────
// 30 days covers the typical incident investigation window and avoids premium
// data retention charges. Increase to 90 if longer trend analysis is needed.
param logRetentionDays = 30

// ── Container App sizing ──────────────────────────────────────────────────────
// siege-api runs Playwright (headless Chromium) for image generation.
// 0.5/1Gi is tight for Playwright — monitor cold start times and upgrade to
// 1.0/2Gi if image generation times out under real load.
param apiCpu = '0.5'
param apiMemory = '1Gi'
param apiMaxReplicas = 3

// Frontend is static content served by Nginx — 0.25/0.5Gi is sufficient.
param frontendCpu = '0.25'
param frontendMemory = '0.5Gi'

// Bot holds a single Discord WebSocket connection — always 1 replica.
// 0.25/0.5Gi is sufficient for connection management and lightweight event handling.
param botCpu = '0.25'
param botMemory = '0.5Gi'

// ── Replica scaling ────────────────────────────────────────────────────────────
// API stays warm in prod — Playwright cold starts on a scaled-to-zero replica
// are too slow for an acceptable user experience.
// Frontend is Nginx only; a 2–3s cold start is acceptable in prod.
param apiMinReplicas = 1
param frontendMinReplicas = 0
