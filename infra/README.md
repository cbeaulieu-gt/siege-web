# Infrastructure

Azure Bicep templates for the Siege Assignment System.

> For a complete end-to-end deployment walkthrough (prerequisites, resource-group setup, secret population, GitHub Actions wiring, DNS, and smoke test), see [docs/self-host/azure.md](../docs/self-host/azure.md).

## Resources provisioned

| Resource | Module |
|---|---|
| Azure Container Registry | `modules/registry.bicep` |
| Log Analytics Workspace | `modules/log-analytics.bicep` |
| Application Insights (workspace-based) | `modules/app-insights.bicep` |
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

## Resource group naming convention

| Environment | Resource group |
|---|---|
| dev | `siege-web-dev` |
| prod | `siege-web-prod` |

## Prerequisites

- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) installed and logged in (`az login`)
- [Bicep CLI](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/install) (`az bicep install`)
- A resource group already created:
  ```bash
  az group create --name siege-web-dev --location australiaeast   # dev
  az group create --name siege-web-prod --location australiaeast  # prod
  ```

## Deploy — development

**Step 1 — provision all infrastructure:**

```bash
cd infra

az deployment group create \
  --resource-group siege-web-dev \
  --template-file main.bicep \
  --parameters main.bicepparam \
  --parameters postgresAdminPassword="$PG_ADMIN_PASSWORD" \
  --parameters discordToken="$DISCORD_TOKEN" \
  --parameters discordBotApiKey="$DISCORD_BOT_API_KEY" \
  --parameters botApiKey="$BOT_API_KEY" \
  --parameters discordGuildId="$DISCORD_GUILD_ID"
```

**Step 2 — push images to ACR:**

> Docker must be running and `az login` must target the same subscription.

```powershell
.\bootstrap-images.ps1
```

## Deploy — production

Production uses `main.prod.bicepparam`. Key differences from dev:

| Concern | Dev | Prod |
|---|---|---|
| ACR SKU | Basic | Standard (geo-replication eligible) |
| PostgreSQL SKU | Standard_B1ms / Burstable | Standard_D2ds_v5 / General Purpose |
| PostgreSQL HA | Disabled | ZoneRedundant (cross-zone standby) |
| PostgreSQL geo-backup | false | true |
| Storage | 32 GB | 64 GB |
| Key Vault soft-delete | 7 days | 90 days |
| Log retention | 30 days | 90 days |
| API CPU / memory | 0.5 vCPU / 1 Gi | 1.0 vCPU / 2 Gi |
| API max replicas | 3 | 5 |
| Frontend CPU / memory | 0.25 vCPU / 0.5 Gi | 0.5 vCPU / 1 Gi |
| Bot CPU / memory | 0.25 vCPU / 0.5 Gi | 0.5 vCPU / 1 Gi |

**Step 1 — provision:**

```bash
cd infra

az deployment group create \
  --resource-group siege-web-prod \
  --template-file main.bicep \
  --parameters main.prod.bicepparam \
  --parameters postgresAdminPassword="$PG_ADMIN_PASSWORD" \
  --parameters discordToken="$DISCORD_TOKEN" \
  --parameters discordBotApiKey="$DISCORD_BOT_API_KEY" \
  --parameters botApiKey="$BOT_API_KEY" \
  --parameters discordGuildId="$DISCORD_GUILD_ID"
```

**Step 2 — push images to ACR:**

```powershell
.\bootstrap-images.ps1   # adjust the registry name to siegeacrprod inside the script
```

**Step 3 — verify deployment:**

```bash
# Check that all three Container Apps are running
az containerapp list \
  --resource-group siege-web-prod \
  --query "[].{name:name, status:properties.runningStatus, fqdn:properties.configuration.ingress.fqdn}" \
  --output table

# Confirm health endpoints respond
curl https://$(az containerapp show \
  --name siege-frontend-prod \
  --resource-group siege-web-prod \
  --query properties.configuration.ingress.fqdn -o tsv)/api/health
```

## Application Insights

All three Container Apps receive `APPLICATIONINSIGHTS_CONNECTION_STRING` as an
environment variable. To enable SDK-level tracing in the Python services, add:

```python
# In backend/app/main.py and bot/app/main.py
from azure.monitor.opentelemetry import configure_azure_monitor
configure_azure_monitor()   # reads APPLICATIONINSIGHTS_CONNECTION_STRING automatically
```

Install the package:

```bash
pip install azure-monitor-opentelemetry
```

For the React frontend, use the `@microsoft/applicationinsights-web` package
and initialise it with the `connectionString` from the environment.

Query live logs in Log Analytics:

```kusto
// Exceptions from the API in the last hour
exceptions
| where timestamp > ago(1h)
| where cloud_RoleName == "siege-api"
| project timestamp, type, outerMessage, customDimensions
| order by timestamp desc
```

## Update a secret in Key Vault

```bash
# Example: rotate the Discord bot token
az keyvault secret set \
  --vault-name {VAULT_NAME} \
  --name discord-token \
  --value "$NEW_DISCORD_TOKEN"

# Force Container Apps to pick up the new secret (create a new revision)
az containerapp update \
  --name siege-bot-prod \
  --resource-group siege-web-prod \
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

> `discord-bot-api-key` and `bot-api-key` must always be rotated together and
> set to the same value. See below for details.

## The bot API key pair

`discord-bot-api-key` and `bot-api-key` are not issued by Discord or Azure —
you generate them yourself. They are a shared secret that secures HTTP
communication between the backend and the bot sidecar.

**Why two parameter names for the same value?**

- `discordBotApiKey` → stored as `discord-bot-api-key` in Key Vault → injected into the **backend** as `DISCORD_BOT_API_KEY`
- `botApiKey` → stored as `bot-api-key` in Key Vault → injected into the **bot** as `BOT_API_KEY`

Both parameters must always carry the same value. If they diverge, backend
requests to the bot will be rejected with 401.

**Generating a key (PowerShell):**

```powershell
[Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Maximum 256 }))
```

## View container logs

```bash
# Stream live logs from the API container
az containerapp logs show \
  --name siege-api-prod \
  --resource-group siege-web-prod \
  --follow

# Query Log Analytics for errors in the last hour
az monitor log-analytics query \
  --workspace {WORKSPACE_ID} \
  --analytics-query "ContainerAppConsoleLogs_CL | where TimeGenerated > ago(1h) | where Log_s contains 'ERROR'"
```

## Scale a Container App

```bash
# Set min/max replicas for the API
az containerapp update \
  --name siege-api-prod \
  --resource-group siege-web-prod \
  --min-replicas 1 \
  --max-replicas 5
```

## Running the Excel import

`bootstrap-excel-import.ps1` connects directly from your local machine to the
Azure PostgreSQL server. It fetches the `database-url` secret from Key Vault
and adds a temporary firewall rule for your public IP automatically — but it
requires your Azure AD account to have read access to Key Vault secrets first.

The Bicep deployment only grants `Key Vault Secrets User` to the Container App
managed identities, not to developer accounts. You must grant it to yourself
once per environment before running the import.

**Step 1 — grant yourself Key Vault Secrets User:**

```powershell
$MyObjectId = az ad signed-in-user show --query id -o tsv
$VaultName  = az keyvault list -g siege-web-prod --query "[0].name" -o tsv

az role assignment create `
  --role "Key Vault Secrets User" `
  --assignee $MyObjectId `
  --scope (az keyvault show --name $VaultName --query id -o tsv)
```

Wait ~30 seconds for the role assignment to propagate.

**Step 2 — run the import:**

```powershell
.\bootstrap-excel-import.ps1 -Environment prod
```

The script will:
1. Fetch `database-url` from Key Vault
2. Add a temporary firewall rule for your current public IP
3. Run the import against the production database
4. Remove the firewall rule automatically when done (even on failure)

> **Dev environment:** substitute `siege-web-dev` for the resource group name
> in the role assignment command, and pass `-Environment dev` to the script.

## Tear down

> This deletes all resources including the database. Ensure backups are taken first.
>
> For production Key Vault: soft-delete retention is 90 days, so the vault name
> will remain reserved for that period. Use `az keyvault purge` to release it
> immediately if you need to redeploy to the same resource group.

```bash
az group delete --name siege-web-prod --yes --no-wait
```
