using 'main.bicep'

// ── Development parameter file ────────────────────────────────────────────────
// Copy to main.prod.bicepparam for production and adjust values.
// Sensitive values (passwords, tokens, keys) MUST be set via environment
// variables or Azure CLI --parameters flags — never commit real secrets here.

param environment = 'dev'
param appPrefix = 'siege-web'
param location = 'westus'
param acrSku = 'Basic'
param imageTag = 'latest'

param postgresAdminUser = 'siegeadmin'
// Set via: --parameters postgresAdminPassword=$PG_ADMIN_PASSWORD
param postgresAdminPassword = ''

// Discord
param discordGuildId = '' // Your Discord server ID (non-secret, ok to fill in)
// Set via: --parameters discordToken=$DISCORD_TOKEN
param discordToken = ''
// Set via: --parameters discordBotApiKey=$DISCORD_BOT_API_KEY
param discordBotApiKey = ''
// Set via: --parameters botApiKey=$BOT_API_KEY
param botApiKey = ''

param postgresGeoRedundantBackup = false
