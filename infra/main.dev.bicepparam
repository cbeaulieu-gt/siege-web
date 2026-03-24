using 'main.bicep'

// ── Development parameter file ────────────────────────────────────────────────
//
// Deploy command:
//
//   az deployment group create \
//     --resource-group siege-rg-dev \
//     --template-file infra/main.bicep \
//     --parameters infra/main.dev.bicepparam \
//     --parameters postgresAdminPassword="$PG_ADMIN_PASSWORD" \
//     --parameters discordToken="$DISCORD_TOKEN" \
//     --parameters discordBotApiKey="$DISCORD_BOT_API_KEY" \
//     --parameters botApiKey="$BOT_API_KEY" \
//     --parameters discordGuildId="$DISCORD_GUILD_ID"
//
// NEVER commit real secrets here. All @secure() params must be supplied at
// deploy time via environment variables or CLI --parameters flags.
//
// Resource group convention:
//   dev  → siege-rg-dev
//   prod → siege-rg-prod
// ─────────────────────────────────────────────────────────────────────────────

param environment = 'dev'
param appPrefix = 'siege-web'
param location = 'westus'

// ── Container Registry ────────────────────────────────────────────────────────
// Basic SKU is sufficient for dev: lower throughput limits and no geo-
// replication, but all required features (push/pull, webhooks) are present.
param acrSku = 'Basic'

// The default generated name 'siegeacrdev' is already taken globally (ACR names
// are unique across all Azure tenants). 'siegewebacr' was confirmed available at
// provisioning time — verify with:
//   az acr check-name --name siegewebacr
param acrNameOverride = 'siegewebacr'

param imageTag = 'latest'

// ── PostgreSQL ────────────────────────────────────────────────────────────────
// Burstable B1ms: 1 vCore (burstable), 2 GiB RAM — sufficient for dev/testing
// workloads. Saves ~$15/month vs B2s. Not eligible for HA; no geo-redundant
// backup. Switch to B2s or GeneralPurpose if load-testing is needed.
param postgresSku = 'Standard_B1ms'
param postgresSkuTier = 'Burstable'
param postgresStorageGB = 32
param postgresBackupRetentionDays = 7
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

// ── Key Vault ─────────────────────────────────────────────────────────────────
// 7-day soft-delete retention is the minimum allowed by Azure and enables fast
// teardown of the dev environment without waiting out a long purge window.
// Do not use 7 days in production — accidental deletion is harder to recover.
param kvSoftDeleteRetentionDays = 7

// ── Log Analytics ─────────────────────────────────────────────────────────────
// 30 days is sufficient for dev debugging. Reduces data ingestion cost while
// still covering a reasonable debugging window for active development.
param logRetentionDays = 30

// ── Container App sizing ──────────────────────────────────────────────────────
// Minimum viable allocations for dev — keeps Container Apps costs low while
// the environment is mostly idle between test sessions.
//
// siege-api runs Playwright (headless Chromium) for image generation.
// 0.5 vCPU / 1 GiB is tight; increase to 1.0/2Gi if browser launch timeouts
// are observed during dev testing.
param apiCpu = '0.5'
param apiMemory = '1Gi'
param apiMaxReplicas = 2

// Frontend is static Nginx — minimal resources needed.
param frontendCpu = '0.25'
param frontendMemory = '0.5Gi'

// Bot holds one Discord WebSocket — always 1 replica; 0.25/0.5Gi is enough
// for the connection and lightweight event handling in dev.
param botCpu = '0.25'
param botMemory = '0.5Gi'

// ── Replica scaling ────────────────────────────────────────────────────────────
// Scale API and frontend to zero when dev is idle. Saves ~$40/month when the
// environment is not being actively used. Trade-off: expect a 5–10s cold start
// after an idle period while the Container App spins up a new replica.
// Bot is excluded — it holds a Discord WebSocket and must stay warm.
param apiMinReplicas = 0
param frontendMinReplicas = 0
