# Siege Assignment App — Operations Runbook

Practical reference for the on-call operator or maintainer. All Azure CLI commands assume
`az login` has been run and the correct subscription is active.

Replace placeholders throughout:

| Placeholder | Example value |
|---|---|
| `{RESOURCE_GROUP}` | `siege-prod-rg` |
| `{CONTAINER_APP_API}` | `siege-api` |
| `{CONTAINER_APP_FRONTEND}` | `siege-frontend` |
| `{CONTAINER_APP_BOT}` | `siege-bot` |
| `{ACR_NAME}` | `siegeacr` |
| `{KEY_VAULT_NAME}` | `siege-kv` |
| `{DB_SERVER_NAME}` | `siege-db` |
| `{DB_NAME}` | `siege` |
| `{LOG_ANALYTICS_WORKSPACE}` | `siege-logs` |
| `{ENVIRONMENT_NAME}` | `siege-env` |

---

## 1. Restarting Containers

### Restart a specific Azure Container App (force new revision)

Azure Container Apps do not have a "restart" button. The recommended restart equivalent is
to force a new revision with the same image:

```bash
# Restart siege-api
az containerapp update \
  --name {CONTAINER_APP_API} \
  --resource-group {RESOURCE_GROUP} \
  --revision-suffix "restart-$(date +%s)"

# Restart siege-frontend
az containerapp update \
  --name {CONTAINER_APP_FRONTEND} \
  --resource-group {RESOURCE_GROUP} \
  --revision-suffix "restart-$(date +%s)"

# Restart siege-bot
az containerapp update \
  --name {CONTAINER_APP_BOT} \
  --resource-group {RESOURCE_GROUP} \
  --revision-suffix "restart-$(date +%s)"
```

### Force a new deployment revision (redeploy latest image)

```bash
# Get the current image tag for siege-api
az containerapp show \
  --name {CONTAINER_APP_API} \
  --resource-group {RESOURCE_GROUP} \
  --query "properties.template.containers[0].image" \
  --output tsv

# Redeploy with the same (or new) image tag
az containerapp update \
  --name {CONTAINER_APP_API} \
  --resource-group {RESOURCE_GROUP} \
  --image {ACR_NAME}.azurecr.io/siege-api:latest
```

### Restart the local docker-compose stack

```bash
# Stop and remove containers, then bring everything back up
docker-compose down
docker-compose up --build

# Restart a single service without rebuilding
docker-compose restart backend

# Full rebuild of a single service
docker-compose up --build backend
```

---

## 2. Rolling Back a Bad Deployment

### Identify the previous good revision

```bash
# List all revisions for siege-api, sorted by creation time
az containerapp revision list \
  --name {CONTAINER_APP_API} \
  --resource-group {RESOURCE_GROUP} \
  --query "sort_by([].{Name:name, Created:properties.createdTime, Active:properties.active, Traffic:properties.trafficWeight}, &Created)" \
  --output table
```

Note the revision name of the last known-good revision (e.g., `siege-api--abc1234`).

### Route traffic back to a previous revision (traffic splitting)

```bash
# Send 100% of traffic to the previous good revision
az containerapp ingress traffic set \
  --name {CONTAINER_APP_API} \
  --resource-group {RESOURCE_GROUP} \
  --revision-weight {PREVIOUS_REVISION_NAME}=100
```

To confirm the traffic weight took effect:

```bash
az containerapp ingress traffic show \
  --name {CONTAINER_APP_API} \
  --resource-group {RESOURCE_GROUP}
```

### Redeploy a specific Docker image tag

```bash
# Deploy a specific tagged image (e.g., a prior build tag like 20260318-abcd123)
az containerapp update \
  --name {CONTAINER_APP_API} \
  --resource-group {RESOURCE_GROUP} \
  --image {ACR_NAME}.azurecr.io/siege-api:{PREVIOUS_TAG}
```

Find available image tags in ACR:

```bash
az acr repository show-tags \
  --name {ACR_NAME} \
  --repository siege-api \
  --orderby time_desc \
  --output table
```

### Roll back the database migration (Alembic downgrade)

> Only do this if the bad deployment included a schema migration. Rolling back the DB
> without rolling back the code (or vice versa) will cause errors.

First, exec into the backend container or run from a machine with DB access and the
`backend/` virtualenv activated:

```bash
# Downgrade one step
alembic downgrade -1

# Downgrade to a specific revision ID (find IDs in backend/alembic/versions/)
alembic downgrade {REVISION_ID}

# Check current head after downgrade
alembic current
```

Then redeploy the previous application image as shown above.

---

## 3. Restoring from Database Backup

Azure PostgreSQL Flexible Server performs automated backups. Point-in-time restore creates
a **new server** from the backup — it does not overwrite the existing server.

### Point-in-time restore

```bash
# Restore to a specific point in time (ISO 8601 UTC)
az postgres flexible-server restore \
  --resource-group {RESOURCE_GROUP} \
  --name {DB_SERVER_NAME}-restored \
  --source-server {DB_SERVER_NAME} \
  --restore-time "2026-03-18T14:00:00Z"
```

This creates a new server named `{DB_SERVER_NAME}-restored`. The operation takes
10–30 minutes depending on database size.

Monitor restore progress:

```bash
az postgres flexible-server show \
  --resource-group {RESOURCE_GROUP} \
  --name {DB_SERVER_NAME}-restored \
  --query "state" \
  --output tsv
# Expected final state: "Ready"
```

### Verify the restore was successful

Connect to the restored server and spot-check key tables:

```bash
# Connect via psql (install psql locally or use Azure Cloud Shell)
psql "host={DB_SERVER_NAME}-restored.postgres.database.azure.com \
      port=5432 \
      dbname={DB_NAME} \
      user={DB_ADMIN_USER} \
      sslmode=require"
```

```sql
-- Verify record counts look correct
SELECT COUNT(*) FROM members;
SELECT COUNT(*) FROM sieges;
SELECT COUNT(*) FROM positions;

-- Check the most recent siege
SELECT id, status, created_at FROM sieges ORDER BY created_at DESC LIMIT 5;

-- Check alembic version is at expected head
SELECT version_num FROM alembic_version;
```

### Reconnect the app to the restored database

1. Update the `database-url` secret in Key Vault to point to the restored server hostname:

```bash
az keyvault secret set \
  --vault-name {KEY_VAULT_NAME} \
  --name "database-url" \
  --value "postgresql+asyncpg://{USER}:{PASSWORD}@{DB_SERVER_NAME}-restored.postgres.database.azure.com/{DB_NAME}"
```

2. Force a new revision on each container app that reads the DB (see Section 4 for the
   full secret rotation + revision procedure):

```bash
az containerapp update \
  --name {CONTAINER_APP_API} \
  --resource-group {RESOURCE_GROUP} \
  --revision-suffix "db-restore-$(date +%s)"
```

3. Hit the health endpoint to confirm DB connectivity:

```bash
curl https://{FRONTEND_URL}/api/health
# Expected: {"status":"ok","db":"connected"}
```

---

## 4. Rotating Secrets

### Secrets inventory

| Secret name (Key Vault) | Used by | Purpose |
|---|---|---|
| `database-url` | `siege-api`, `siege-bot` | PostgreSQL connection string (asyncpg format) |
| `discord-token` | `siege-bot` | Bot login token for the Discord API |
| `discord-guild-id` | `siege-api`, `siege-bot` | Targets the correct Discord server |
| `discord-bot-api-key` | `siege-api` | Auth header sent from backend → bot HTTP sidecar |
| `bot-api-key` | `siege-bot` | Validates inbound requests on the bot HTTP API |

Note: `discord-bot-api-key` (the key the backend uses to call the bot) and `bot-api-key`
(the key the bot validates against) must always match. Rotate them together.

### Update a secret in Azure Key Vault

```bash
# Example: rotate the discord-token
az keyvault secret set \
  --vault-name {KEY_VAULT_NAME} \
  --name "discord-token" \
  --value "{NEW_TOKEN_VALUE}"
```

Confirm the new version is active:

```bash
az keyvault secret show \
  --vault-name {KEY_VAULT_NAME} \
  --name "discord-token" \
  --query "{Version:id, Updated:attributes.updated}" \
  --output table
```

### Force Container Apps to pick up updated Key Vault secrets

Container Apps cache secrets at revision creation time. A new revision must be created
to pick up the updated value.

```bash
# Force new revision for siege-api (picks up database-url, discord-guild-id, discord-bot-api-key)
az containerapp update \
  --name {CONTAINER_APP_API} \
  --resource-group {RESOURCE_GROUP} \
  --revision-suffix "secret-rotation-$(date +%s)"

# Force new revision for siege-bot (picks up discord-token, discord-guild-id, bot-api-key, database-url)
az containerapp update \
  --name {CONTAINER_APP_BOT} \
  --resource-group {RESOURCE_GROUP} \
  --revision-suffix "secret-rotation-$(date +%s)"
```

After the new revisions are active, verify the health endpoints (see Section 6) to confirm
the app reconnected correctly with the new secret values.

---

## 5. Viewing Logs

### Stream live logs from Azure Container Apps

```bash
# Stream logs from siege-api (most recent 20 lines + follow)
az containerapp logs show \
  --name {CONTAINER_APP_API} \
  --resource-group {RESOURCE_GROUP} \
  --follow \
  --tail 20

# Stream logs from siege-bot
az containerapp logs show \
  --name {CONTAINER_APP_BOT} \
  --resource-group {RESOURCE_GROUP} \
  --follow \
  --tail 20

# Stream from a specific revision
az containerapp logs show \
  --name {CONTAINER_APP_API} \
  --resource-group {RESOURCE_GROUP} \
  --revision {REVISION_NAME} \
  --follow
```

### Query logs in Log Analytics Workspace

Open the Azure portal → Log Analytics Workspaces → `{LOG_ANALYTICS_WORKSPACE}` → Logs,
or run queries via CLI:

```bash
# Errors from siege-api in the last hour
az monitor log-analytics query \
  --workspace {LOG_ANALYTICS_WORKSPACE} \
  --analytics-query "
    ContainerAppConsoleLogs_CL
    | where ContainerAppName_s == '{CONTAINER_APP_API}'
    | where Log_s has 'ERROR'
    | where TimeGenerated > ago(1h)
    | project TimeGenerated, Log_s
    | order by TimeGenerated desc
    | take 100
  " \
  --output table

# Slow requests (>2s) from siege-api
az monitor log-analytics query \
  --workspace {LOG_ANALYTICS_WORKSPACE} \
  --analytics-query "
    ContainerAppConsoleLogs_CL
    | where ContainerAppName_s == '{CONTAINER_APP_API}'
    | where Log_s has 'duration'
    | extend duration_ms = extract('duration_ms=(\\\\d+)', 1, Log_s)
    | where toint(duration_ms) > 2000
    | project TimeGenerated, Log_s, duration_ms
    | order by TimeGenerated desc
  " \
  --output table
```

### Reading backend structured logs

The FastAPI backend emits structured JSON logs. Key fields to filter on:

| Field | Purpose | Example |
|---|---|---|
| `request_id` | Correlates all log lines for a single HTTP request | `"req_abc123"` |
| `siege_id` | Identifies which siege the operation is for | `42` |
| `member_id` | Identifies which member an operation concerns | `17` |
| `level` | Log severity | `INFO`, `WARNING`, `ERROR` |
| `path` | HTTP path | `"/api/sieges/42/board"` |
| `duration_ms` | Request duration in milliseconds | `312` |

To find all log lines for a specific request:

```bash
az monitor log-analytics query \
  --workspace {LOG_ANALYTICS_WORKSPACE} \
  --analytics-query "
    ContainerAppConsoleLogs_CL
    | where ContainerAppName_s == '{CONTAINER_APP_API}'
    | where Log_s has '{REQUEST_ID}'
    | project TimeGenerated, Log_s
    | order by TimeGenerated asc
  " \
  --output table
```

---

## 6. Monitoring and Alerts

### What to watch

| Signal | Threshold | Action |
|---|---|---|
| 5xx error rate | > 1% over 5 min | Check recent deployment; check DB connectivity |
| Request duration (p95) | > 3 seconds | Check `/api/sieges/{id}/board` query plan; check connection pool |
| Bot container restarts | Any | Check Discord token validity; check `discord-guild-id` config |
| DB connection errors | Any | Check `database-url` secret; check firewall rules; check pool exhaustion |
| Image generation duration | > 10 seconds | Playwright cold start in wrong container; check `siege-api` container |

These signals should be configured as Azure Monitor alerts pointing to the Log Analytics
Workspace and Application Insights resource.

### Health endpoints

**Backend health** (public via frontend proxy):

```bash
curl https://{FRONTEND_URL}/api/health
# Expected:
# {"status":"ok","db":"connected"}
```

**Bot health** (internal only — run from siege-api container or via az containerapp exec):

```bash
# Exec into the siege-api container and call the bot sidecar
az containerapp exec \
  --name {CONTAINER_APP_API} \
  --resource-group {RESOURCE_GROUP} \
  --command "curl -s http://siege-bot:8001/api/health"
# Expected:
# {"status":"ok","discord_connected":true}
```

### Post-launch 48-hour checklist

Within the first 48 hours after a production deployment, verify:

- [ ] `GET /api/health` returns `{"status":"ok","db":"connected"}` continuously
- [ ] Bot health returns `{"discord_connected":true}`
- [ ] Application Insights shows no spike in 5xx errors
- [ ] At least one full siege workflow completed end-to-end (create → assign → validate → activate)
- [ ] DM notification batch completes without errors for all members
- [ ] Image generation completes in under 5 seconds
- [ ] Channel post delivers images to Discord successfully
- [ ] Assignment board loads in under 2 seconds with a full 30-building siege
- [ ] No unusual log volume in Log Analytics (check for repeated errors or connection retries)
- [ ] Automated PostgreSQL backup confirmed enabled:
  ```bash
  az postgres flexible-server show \
    --resource-group {RESOURCE_GROUP} \
    --name {DB_SERVER_NAME} \
    --query "backup" \
    --output json
  ```

---

## 7. Common Incident Playbooks

### Bot not sending DMs

**Symptoms:** DM notification batch shows all results as failed. Bot health endpoint
returns `{"discord_connected":false}` or times out.

**Steps:**

1. Check bot container health:
   ```bash
   az containerapp show \
     --name {CONTAINER_APP_BOT} \
     --resource-group {RESOURCE_GROUP} \
     --query "properties.runningStatus" \
     --output tsv
   ```

2. Check recent bot logs for connection errors:
   ```bash
   az containerapp logs show \
     --name {CONTAINER_APP_BOT} \
     --resource-group {RESOURCE_GROUP} \
     --tail 50
   ```
   Look for: `discord.errors.LoginFailure`, `Forbidden`, `Invalid token`.

3. Verify the Discord token is valid — log into the Discord Developer Portal and confirm
   the bot token has not been reset. If it has been reset, rotate `discord-token` in
   Key Vault (see Section 4) and force a new bot revision.

4. Verify `discord-guild-id` matches the actual guild:
   ```bash
   az keyvault secret show \
     --vault-name {KEY_VAULT_NAME} \
     --name "discord-guild-id" \
     --query "value" \
     --output tsv
   ```
   Cross-check with the guild ID visible in Discord (Settings → Advanced → Developer Mode,
   then right-click the server).

5. Verify `bot-api-key` and `discord-bot-api-key` match:
   ```bash
   az keyvault secret show --vault-name {KEY_VAULT_NAME} --name "bot-api-key" --query "value" -o tsv
   az keyvault secret show --vault-name {KEY_VAULT_NAME} --name "discord-bot-api-key" --query "value" -o tsv
   ```
   If they differ, update `discord-bot-api-key` to match and force a new `siege-api` revision.

6. If all config looks correct, restart the bot container (see Section 1) and re-trigger
   the notification batch.

---

### Board loads slowly

**Symptoms:** `GET /api/sieges/{id}/board` takes more than 2–3 seconds. Frontend board
page shows a spinner for an extended period.

**Steps:**

1. Check if Playwright is running in `siege-api` unexpectedly (image generation is
   CPU-intensive and should only fire on explicit requests):
   ```bash
   az containerapp logs show \
     --name {CONTAINER_APP_API} \
     --resource-group {RESOURCE_GROUP} \
     --tail 100 | grep -i playwright
   ```
   If Playwright log lines appear during board requests, there is a code path triggering
   image generation incorrectly. Roll back to the previous revision.

2. Check DB query duration in Application Insights or Log Analytics for slow board queries.
   The board endpoint issues nested queries for buildings → groups → positions — an N+1
   issue here will be visible as many short queries in rapid succession.

3. Check PostgreSQL connection pool exhaustion:
   ```bash
   az monitor log-analytics query \
     --workspace {LOG_ANALYTICS_WORKSPACE} \
     --analytics-query "
       ContainerAppConsoleLogs_CL
       | where ContainerAppName_s == '{CONTAINER_APP_API}'
       | where Log_s has 'QueuePool limit'
       | project TimeGenerated, Log_s
       | order by TimeGenerated desc
       | take 20
     " \
     --output table
   ```
   If pool exhaustion is found, consider scaling out the Container App or increasing the
   SQLAlchemy pool size in `backend/app/db/session.py`.

4. If the issue is isolated to one large siege, check how many buildings, groups, and
   positions it has. A siege with all 30 buildings at max level has ~200+ positions.
   This is the expected maximum load.

---

### Deployment stuck

**Symptoms:** GitHub Actions shows a successful image push to ACR, but the Container App
is still running the old revision or the new revision shows a failed status.

**Steps:**

1. Check ACR push succeeded:
   ```bash
   az acr repository show-tags \
     --name {ACR_NAME} \
     --repository siege-api \
     --orderby time_desc \
     --output table
   ```
   The new tag should appear at the top. If it is missing, the Docker build or push failed
   in CI — check the GitHub Actions run logs.

2. Check the Container App revision status:
   ```bash
   az containerapp revision list \
     --name {CONTAINER_APP_API} \
     --resource-group {RESOURCE_GROUP} \
     --query "[].{Name:name, Status:properties.runningState, Created:properties.createdTime}" \
     --output table
   ```
   A revision in `Failed` or `Degraded` state means the container crashed at startup.

3. Get logs from the failed revision:
   ```bash
   az containerapp logs show \
     --name {CONTAINER_APP_API} \
     --resource-group {RESOURCE_GROUP} \
     --revision {FAILED_REVISION_NAME} \
     --tail 100
   ```
   Common causes:
   - Missing environment variable or Key Vault reference that couldn't be resolved
   - Application crash on startup (import error, missing migration, etc.)
   - Image pull failure (wrong tag, ACR auth misconfigured)

4. Verify Key Vault references are resolving. In the Azure portal, navigate to the
   Container App → Secrets and check for any red warning icons indicating a failed
   Key Vault reference.

5. If the new revision is broken, route traffic back to the previous revision
   (see Section 2) while investigating.

---

### Database connection errors

**Symptoms:** Backend logs show `asyncpg.exceptions.ConnectionDoesNotExistError`,
`could not connect to server`, or 500 errors on any endpoint that touches the database.

**Steps:**

1. Verify the `database-url` secret is correctly formed:
   ```bash
   az keyvault secret show \
     --vault-name {KEY_VAULT_NAME} \
     --name "database-url" \
     --query "value" \
     --output tsv
   ```
   Expected format: `postgresql+asyncpg://{USER}:{PASSWORD}@{HOST}/{DB_NAME}`
   Confirm the hostname resolves and the database name is correct.

2. Check PostgreSQL server status:
   ```bash
   az postgres flexible-server show \
     --resource-group {RESOURCE_GROUP} \
     --name {DB_SERVER_NAME} \
     --query "{State:state, FQDN:fullyQualifiedDomainName}" \
     --output table
   ```
   Expected state: `Ready`. If `Stopped`, restart it:
   ```bash
   az postgres flexible-server start \
     --resource-group {RESOURCE_GROUP} \
     --name {DB_SERVER_NAME}
   ```

3. Check PostgreSQL firewall rules. The Container Apps environment's outbound IP range
   must be allowed:
   ```bash
   # List current firewall rules
   az postgres flexible-server firewall-rule list \
     --resource-group {RESOURCE_GROUP} \
     --name {DB_SERVER_NAME} \
     --output table

   # Get the Container Apps environment outbound IP(s)
   az containerapp env show \
     --name {ENVIRONMENT_NAME} \
     --resource-group {RESOURCE_GROUP} \
     --query "properties.staticIp" \
     --output tsv
   ```
   Add a firewall rule if the Container App IP is not listed:
   ```bash
   az postgres flexible-server firewall-rule create \
     --resource-group {RESOURCE_GROUP} \
     --name {DB_SERVER_NAME} \
     --rule-name "container-apps-outbound" \
     --start-ip-address {CONTAINER_APP_OUTBOUND_IP} \
     --end-ip-address {CONTAINER_APP_OUTBOUND_IP}
   ```

4. Check for connection pool exhaustion (see Board loads slowly, Step 3 above).
   If the pool is exhausted, restarting the `siege-api` Container App (Section 1) will
   reset all connections as a temporary fix while you investigate the root cause.
