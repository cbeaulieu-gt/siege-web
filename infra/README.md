# Infrastructure

Azure Bicep templates for the Siege Assignment System.

## Resources provisioned

| Resource | Module |
|---|---|
| Azure Container Registry | `modules/registry.bicep` |
| Log Analytics Workspace | `modules/log-analytics.bicep` |
| PostgreSQL Flexible Server | `modules/postgres.bicep` |
| Azure Key Vault | `modules/keyvault.bicep` |
| Container Apps Environment | `modules/container-env.bicep` |
| Container Apps (api, frontend, bot) | `modules/container-apps.bicep` |
| Key Vault role assignments (Secrets User) | `main.bicep` |

Key Vault role assignments are created directly in `main.bicep` after the
Container Apps module runs, using their system-assigned managed identity
principal IDs. This is a single-pass deployment — no manual role assignment
step is required.

## ACR naming

The registry name follows a fixed pattern: `${appPrefix}acr${environment}`.

| Environment | Registry name | Login server |
|---|---|---|
| dev | `siegeacrdev` | `siegeacrdev.azurecr.io` |
| prod | `siegeacrprod` | `siegeacrprod.azurecr.io` |

## Prerequisites

- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) installed and logged in (`az login`)
- [Bicep CLI](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/install) (`az bicep install`)
- A resource group already created:
  ```bash
  az group create --name {RESOURCE_GROUP} --location australiaeast
  ```

## Deploy from scratch

**Step 1 — provision all infrastructure (single pass):**

```bash
cd infra

az deployment group create \
  --resource-group {RESOURCE_GROUP} \
  --template-file main.bicep \
  --parameters main.bicepparam \
  --parameters postgresAdminPassword="$PG_ADMIN_PASSWORD" \
  --parameters discordToken="$DISCORD_TOKEN" \
  --parameters discordBotApiKey="$DISCORD_BOT_API_KEY" \
  --parameters botApiKey="$BOT_API_KEY" \
  --parameters discordGuildId="$DISCORD_GUILD_ID"
```

This creates all resources including the Container Apps and their Key Vault
role assignments in one pass. No second run required.

**Step 2 — push images to ACR (run once from the repo root):**

> **Prerequisite:** Docker must be running and you must be logged in to Azure
> (`az login`) in the same subscription as the resource group.

```powershell
.\bootstrap-images.ps1
```

This builds `siege-api`, `siege-frontend`, and `siege-bot` locally and pushes
them to the registry. Container Apps pull images using ACR admin credentials
(managed automatically by Bicep via `listCredentials()`).

After this step the Container Apps will pull the images on their next restart
and the health checks should pass.

## Deploy to production

Create `main.prod.bicepparam` (copy `main.bicepparam`, set `environment = 'prod'`,
`acrSku = 'Standard'`, `postgresGeoRedundantBackup = true`), then:

```bash
az deployment group create \
  --resource-group {RESOURCE_GROUP_PROD} \
  --template-file main.bicep \
  --parameters main.prod.bicepparam \
  --parameters postgresAdminPassword="$PG_ADMIN_PASSWORD" \
  --parameters discordToken="$DISCORD_TOKEN" \
  --parameters discordBotApiKey="$DISCORD_BOT_API_KEY" \
  --parameters botApiKey="$BOT_API_KEY" \
  --parameters discordGuildId="$DISCORD_GUILD_ID"
```

The GitHub Actions deploy workflow (`deploy.yml`) targets `siegeacrprod` and
the `siege-*-prod` Container Apps. Merge to `main` to trigger it after the
infrastructure is provisioned.

## Update a secret in Key Vault

```bash
# Example: rotate the Discord bot token
az keyvault secret set \
  --vault-name {VAULT_NAME} \
  --name discord-token \
  --value "$NEW_DISCORD_TOKEN"

# Force Container Apps to pick up the new secret (create a new revision)
az containerapp update \
  --name siege-bot-{ENV} \
  --resource-group {RESOURCE_GROUP} \
  --revision-suffix "secret-rotate-$(date +%Y%m%d)"
```

Secrets and their consumers:

| Secret name | Used by |
|---|---|
| `database-url` | siege-api, siege-bot |
| `discord-token` | siege-bot |
| `discord-guild-id` | siege-api, siege-bot (as plain env var) |
| `discord-bot-api-key` | siege-api → siege-bot HTTP auth |
| `bot-api-key` | siege-bot inbound auth validation |

> **Important:** `discord-bot-api-key` and `bot-api-key` must always be rotated
> together and set to the same value.

## The bot API key pair

`discord-bot-api-key` and `bot-api-key` are not issued by Discord or Azure — you generate them yourself. They are a shared secret that secures HTTP communication between the backend and the bot sidecar.

**Why two parameter names for the same value?**

The Bicep deployment separates them because they are injected into different services:

- `discordBotApiKey` → stored as `discord-bot-api-key` in Key Vault → injected into the **backend** as `DISCORD_BOT_API_KEY` for outbound calls to the bot HTTP API
- `botApiKey` → stored as `bot-api-key` in Key Vault → injected into the **bot** as `BOT_API_KEY` for inbound request validation

Both parameters must always carry the same value. If they ever diverge, the backend's requests to the bot will be rejected with 401.

**Generating a key**

Run this in PowerShell to produce a random 32-byte base64 string:

```powershell
[Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Maximum 256 }))
```

Pass the output as both `discordBotApiKey` and `botApiKey` when deploying, and store it somewhere safe (e.g. a local `.env` file or a password manager) so you can supply it again on future deployments.

## View container logs

```bash
# Stream live logs from the API container
az containerapp logs show \
  --name siege-api-{ENV} \
  --resource-group {RESOURCE_GROUP} \
  --follow

# Query Log Analytics for errors in the last hour
az monitor log-analytics query \
  --workspace {WORKSPACE_ID} \
  --analytics-query "ContainerAppConsoleLogs_CL | where TimeGenerated > ago(1h) | where Log_s contains 'ERROR'"
```

## Scale a container app

```bash
# Set min/max replicas for the API
az containerapp update \
  --name siege-api-{ENV} \
  --resource-group {RESOURCE_GROUP} \
  --min-replicas 1 \
  --max-replicas 5
```

## Tear down

> ⚠️ This deletes all resources including the database. Ensure backups are taken first.

```bash
az group delete --name {RESOURCE_GROUP} --yes --no-wait
```
