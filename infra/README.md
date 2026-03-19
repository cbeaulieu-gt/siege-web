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

## Prerequisites

- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) installed and logged in (`az login`)
- [Bicep CLI](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/install) (`az bicep install`)
- A resource group already created:
  ```bash
  az group create --name {RESOURCE_GROUP} --location australiaeast
  ```

## Deploy from scratch

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

> **Note:** The first deployment creates Key Vault before Container Apps exist,
> so managed identity role assignments use an empty `containerAppPrincipalIds`
> array. After the first deploy, retrieve the principal IDs from the outputs and
> run the deployment a second time to grant Key Vault access:
>
> ```bash
> API_PRINCIPAL=$(az containerapp show -g {RESOURCE_GROUP} -n siege-api-dev --query identity.principalId -o tsv)
> BOT_PRINCIPAL=$(az containerapp show -g {RESOURCE_GROUP} -n siege-bot-dev --query identity.principalId -o tsv)
> ```
> Then pass them to the keyvault module (or assign the role manually):
> ```bash
> az role assignment create \
>   --assignee $API_PRINCIPAL \
>   --role "Key Vault Secrets User" \
>   --scope $(az keyvault show -g {RESOURCE_GROUP} -n {VAULT_NAME} --query id -o tsv)
> ```

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
