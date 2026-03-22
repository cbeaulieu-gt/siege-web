# TODO

- [x] Write Playwright E2E tests for the siege lifecycle and supporting pages
- [x] Fix 22 failing Playwright E2E tests (Date.now() uniqueness, strict-mode selector violations, member bucket selector, row-count race)
- [x] Fix three Azure Container Apps health check failures (KV role assignments, nginx envsubst variable bleed, ACR name mismatch)
- [x] Write Vitest component tests: BoardPage (position cell states, context menu actions, member bucket) and notification polling (SiegeSettingsPage)
- [x] Author Bicep IaC for production environment
  - [x] New `infra/modules/app-insights.bicep` (workspace-based Application Insights)
  - [x] Updated `infra/modules/log-analytics.bicep` (retentionInDays param + resourceId output)
  - [x] Updated `infra/modules/postgres.bicep` (SKU/tier/storage/HA/backup-retention params)
  - [x] Updated `infra/modules/keyvault.bicep` (softDeleteRetentionDays param)
  - [x] Updated `infra/modules/container-apps.bicep` (App Insights env var, CPU/memory params)
  - [x] Updated `infra/main.bicep` (all new params wired through, app-insights module added)
  - [x] New `infra/main.prod.bicepparam` (D2ds_v5, ZoneRedundant HA, geo-backup, 90-day retention)
  - [x] Updated `infra/README.md` (production deploy steps, comparison table, App Insights SDK notes)
