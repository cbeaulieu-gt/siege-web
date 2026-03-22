using 'main.bicep'

// ── Production parameter file ─────────────────────────────────────────────────
//
// Deploy command:
//
//   az deployment group create \
//     --resource-group siege-rg-prod \
//     --template-file main.bicep \
//     --parameters main.prod.bicepparam \
//     --parameters postgresAdminPassword="$PG_ADMIN_PASSWORD" \
//     --parameters discordToken="$DISCORD_TOKEN" \
//     --parameters discordBotApiKey="$DISCORD_BOT_API_KEY" \
//     --parameters botApiKey="$BOT_API_KEY" \
//     --parameters discordGuildId="$DISCORD_GUILD_ID"
//
// NEVER commit real secrets here. All @secure() params must be supplied at
// deploy time via environment variables or a CI/CD secret store.
//
// Resource group convention:
//   dev  → siege-rg-dev
//   prod → siege-rg-prod
// ─────────────────────────────────────────────────────────────────────────────

param environment = 'prod'
param appPrefix = 'siege'
param location = 'australiaeast'

// ── Container Registry ────────────────────────────────────────────────────────
// Standard SKU enables geo-replication, content trust, and higher throughput
// pull limits compared to Basic. Required for production workloads.
param acrSku = 'Standard'

param imageTag = 'latest'

// ── PostgreSQL ────────────────────────────────────────────────────────────────
// General Purpose D2ds_v5: 2 dedicated vCores, 8 GiB RAM — the minimum tier
// eligible for zone-redundant high availability. Switch to D4ds_v5 if query
// latency becomes a bottleneck (doubles cost).
//
// ZoneRedundant HA provisions a standby replica in a different availability
// zone. On a zone failure Azure promotes the standby automatically (typically
// <30 seconds). SameZone is cheaper but doesn't protect against a zone outage.
param postgresSku = 'Standard_D2ds_v5'
param postgresSkuTier = 'GeneralPurpose'
param postgresStorageGB = 64
param postgresBackupRetentionDays = 7   // increase to 35 for maximum retention
param postgresGeoRedundantBackup = true
param postgresHighAvailability = 'ZoneRedundant'

param postgresAdminUser = 'siegeadmin'
// Supply at deploy time: --parameters postgresAdminPassword="$PG_ADMIN_PASSWORD"
param postgresAdminPassword = ''

// ── Discord secrets ───────────────────────────────────────────────────────────
param discordGuildId = '' // Your Discord server ID (non-secret; ok to fill in)
// Supply at deploy time:
param discordToken = ''
param discordBotApiKey = ''
param botApiKey = ''

// ── Key Vault ─────────────────────────────────────────────────────────────────
// 90-day soft-delete retention gives the maximum recovery window for secrets
// accidentally deleted or overwritten. The dev value of 7 days enables fast
// teardown of test environments but is not appropriate for production.
param kvSoftDeleteRetentionDays = 90

// ── Log Analytics ─────────────────────────────────────────────────────────────
// 90 days matches the Application Insights retention and gives enough history
// for incident investigations and trend analysis without premium data charges.
param logRetentionDays = 90

// ── Container App sizing ──────────────────────────────────────────────────────
// siege-api runs Playwright (headless Chromium) for image generation.
// 1.0 vCPU / 2 GiB is the minimum allocation that keeps browser launch times
// acceptable. Scale to 2.0/4Gi if P95 latency on image generation is too high.
param apiCpu = '1.0'
param apiMemory = '2Gi'
param apiMaxReplicas = 5

// Frontend is static content served by Nginx — 0.5/1Gi gives comfortable
// headroom for spiky clan-activity periods.
param frontendCpu = '0.5'
param frontendMemory = '1Gi'

// Bot holds a single Discord WebSocket connection — always 1 replica.
// 0.5/1Gi gives enough room for Playwright if the bot generates its own images.
param botCpu = '0.5'
param botMemory = '1Gi'
