// monitoring.bicep — Alert action group + scheduled query rules for siege-api and siege-bot.
//
// API versions confirmed stable GA as of 2026-04-29:
//   Microsoft.Insights/actionGroups         → 2023-01-01
//   Microsoft.Insights/scheduledQueryRules  → 2023-12-01 (upgraded from plan's 2023-03-15-preview)
//
// Scope: resource group (default).
// This module is invoked from main.bicep after the appInsights module so the
// App Insights resource ID is available as an input.

@description('Azure region for all resources')
param location string

@description('Environment name (dev or prod)')
@allowed(['dev', 'prod'])
param environment string

@description('Short prefix used in resource names')
param appPrefix string

@description('Resource ID of the Application Insights instance to scope alerts against')
param appInsightsId string

@description('Name of the Application Insights instance (used in the workbook resource added in Phase 3)')
#disable-next-line no-unused-params
param appInsightsName string

@description('Email address that receives alert notifications')
param alertEmail string

@description('Resource tags to apply to all monitoring resources')
param tags object = {
  project: appPrefix
  environment: environment
}

// ── Action Group ─────────────────────────────────────────────────────────────
//
// One email-only action group per environment. `groupShortName` is capped at
// 12 characters by the Azure API — "siege-dev" (9) and "siege-prod" (10) are
// within limit.

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: 'siege-app-health-${environment}'
  location: 'Global'    // Action groups are always global resources
  tags: tags
  properties: {
    groupShortName: 'siege-${environment}'   // ≤12 chars: 'siege-dev' = 9, 'siege-prod' = 10
    enabled: true
    emailReceivers: [
      {
        name: 'On-Call Email'
        emailAddress: alertEmail
        useCommonAlertSchema: true  // structured fields in the email body — easier to parse
      }
    ]
    armRoleReceivers: []
    azureAppPushReceivers: []
    azureFunctionReceivers: []
    eventHubReceivers: []
    itsmReceivers: []
    logicAppReceivers: []
    smsReceivers: []
    voiceReceivers: []
    webhookReceivers: []
  }
}

// ── Alert rules ───────────────────────────────────────────────────────────────
//
// Each alert is a log-search alert scoped to the App Insights resource.
// Common settings:
//   - evaluationFrequency PT1M — check every minute
//   - severity 2 (warning) or 3 (informational)
//   - autoMitigate true — alert resolves automatically when condition clears
//   - muteActionsDuration PT15M — suppresses repeat emails during an incident
//
// All KQL queries are written to return zero rows in the steady state and ≥1
// row when the condition is breached, so `operator: GreaterThan, threshold: 0`
// works uniformly across all five rules.
//
// NOTE: windowSize must be >= evaluationFrequency per Azure validation rules.
// Both are ISO 8601 duration strings.

// ── Alert 1: API 5xx rate > 1% over 5 min ────────────────────────────────────
// Severity 2 — page-worthy; the API is returning errors to real users.
// Min-traffic floor (total >= 20) prevents false alarms during idle windows.

resource alert5xxRate 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = {
  name: '${appPrefix}-alert-5xx-rate-${environment}'
  location: location
  tags: tags
  properties: {
    displayName: '[${environment}] siege-api — 5xx error rate > 1%'
    description: 'Fires when more than 1% of API requests return HTTP 5xx over a 5-minute window. Floor: ≥20 total requests (suppresses low-traffic noise).'
    enabled: true
    severity: 2
    evaluationFrequency: 'PT1M'
    windowSize: 'PT5M'
    scopes: [appInsightsId]
    autoMitigate: true
    muteActionsDuration: 'PT15M'
    criteria: {
      allOf: [
        {
          query: '''
requests
| where timestamp > ago(5m)
| where cloud_RoleName == "siege-api"
| summarize total = count(), errors = countif(toint(resultCode) >= 500)
| where total >= 20  // suppress alert when traffic is too low to be statistically meaningful
| extend errorRate = todouble(errors) / total
| where errorRate > 0.01
| project errorRate, errors, total
'''
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 0
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: [actionGroup.id]
    }
  }
}

// ── Alert 2: API request latency p95 > 3s ────────────────────────────────────
// Severity 3 — warning; latency is degraded but requests are still succeeding.
// Min-traffic floor (sampleCount >= 20) avoids false alarms from a single slow call.

resource alertLatencyP95 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = {
  name: '${appPrefix}-alert-latency-p95-${environment}'
  location: location
  tags: tags
  properties: {
    displayName: '[${environment}] siege-api — p95 latency > 3s'
    description: 'Fires when the 95th-percentile request duration exceeds 3000ms over a 5-minute window. Floor: ≥20 requests.'
    enabled: true
    severity: 3
    evaluationFrequency: 'PT1M'
    windowSize: 'PT5M'
    scopes: [appInsightsId]
    autoMitigate: true
    muteActionsDuration: 'PT15M'
    criteria: {
      allOf: [
        {
          query: '''
requests
| where timestamp > ago(5m)
| where cloud_RoleName == "siege-api"
| summarize p95 = percentile(duration, 95), sampleCount = count()
| where sampleCount >= 20
| where p95 > 3000  // duration is milliseconds in App Insights
| project p95, sampleCount
'''
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 0
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: [actionGroup.id]
    }
  }
}

// ── Alert 3: Bot restart ──────────────────────────────────────────────────────
// Severity 2 — page-worthy; the bot holds a Discord WebSocket — any restart is
// notable. Window PT1M / frequency PT1M → a single restart pages immediately.
//
// TODO(#246-phase5): The `has_any` predicate uses placeholder startup strings.
// After the first dev deploy, run:
//   traces | where cloud_RoleName == "siege-bot" | order by timestamp desc | take 50
// and replace the list with the string(s) the bot actually emits on connect.
// Safe placeholder: "Logged in as" (discord.py logs this on successful login)
// and "ready" as a fallback.

resource alertBotRestart 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = {
  name: '${appPrefix}-alert-bot-restart-${environment}'
  location: location
  tags: tags
  properties: {
    displayName: '[${environment}] siege-bot — unexpected restart detected'
    description: 'Fires when any siege-bot startup trace is observed in a 1-minute window, indicating the bot process restarted. Phase 5 will confirm the exact startup log string.'
    enabled: true
    severity: 2
    evaluationFrequency: 'PT1M'
    windowSize: 'PT1M'
    scopes: [appInsightsId]
    autoMitigate: true
    muteActionsDuration: 'PT15M'
    criteria: {
      allOf: [
        {
          // TODO(#246-phase5): Confirm actual bot startup log string(s) from dev traces.
          // Current placeholder: discord.py logs "Logged in as <BotName>#XXXX" on successful
          // gateway connect. "ready" is included as a secondary fallback.
          query: '''
traces
| where timestamp > ago(1m)
| where cloud_RoleName == "siege-bot"
| where message has_any ("Logged in as", "ready")
| summarize restartEvents = count()
| where restartEvents > 0
| project restartEvents
'''
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 0
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: [actionGroup.id]
    }
  }
}

// ── Alert 4: DB connection error ──────────────────────────────────────────────
// Severity 2 — page-worthy; any DB connectivity failure is a service-impacting event.
// Unions exceptions (asyncpg error types) with failed PostgreSQL dependencies.

resource alertDbConnectionError 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = {
  name: '${appPrefix}-alert-db-connection-${environment}'
  location: location
  tags: tags
  properties: {
    displayName: '[${environment}] siege-api — DB connection error'
    description: 'Fires when any PostgreSQL connection error (asyncpg exception or failed dependency) is observed in a 5-minute window.'
    enabled: true
    severity: 2
    evaluationFrequency: 'PT1M'
    windowSize: 'PT5M'
    scopes: [appInsightsId]
    autoMitigate: true
    muteActionsDuration: 'PT15M'
    criteria: {
      allOf: [
        {
          query: '''
union
  (exceptions
    | where cloud_RoleName == "siege-api"
    | where timestamp > ago(5m)
    | where type has_any ("OperationalError", "InterfaceError", "ConnectionDoesNotExistError", "asyncpg")
        or outerMessage has_any ("could not connect", "connection refused", "connection reset", "server closed the connection")),
  (dependencies
    | where cloud_RoleName == "siege-api"
    | where timestamp > ago(5m)
    | where (type == "PostgreSQL" or target contains ".postgres.database.azure.com") and success == false)
| summarize errors = count()
| where errors > 0
| project errors
'''
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 0
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: [actionGroup.id]
    }
  }
}

// ── Alert 5: Image generation > 10s ──────────────────────────────────────────
// Severity 3 — warning; slow renders degrade UX but requests still complete.
//
// Route confirmed: POST /sieges/{siege_id}/generate-images
// Operation name in App Insights requests table for FastAPI routes follows the
// pattern "POST /sieges/{siege_id}/generate-images".
//
// This alert queries the `requests` table filtered by operation_Name matching
// the image generation route, rather than relying on a `customEvents` row.
// If the API begins emitting a custom "image_generation" event with duration_ms
// in Phase 5, the query can be updated to use customEvents for more precision.
//
// TODO(#246-phase5): Verify the exact operation_Name value emitted by FastAPI
// in App Insights for this route. If the parameterized form differs (e.g.
// "POST /sieges/*/generate-images"), update the `has` predicate accordingly.

resource alertImageGenSlow 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = {
  name: '${appPrefix}-alert-image-gen-slow-${environment}'
  location: location
  tags: tags
  properties: {
    displayName: '[${environment}] siege-api — image generation > 10s'
    description: 'Fires when any request to the generate-images route takes longer than 10 seconds in a 5-minute window. Queries the requests table by route name (no customEvents dependency).'
    enabled: true
    severity: 3
    evaluationFrequency: 'PT1M'
    windowSize: 'PT5M'
    scopes: [appInsightsId]
    autoMitigate: true
    muteActionsDuration: 'PT15M'
    criteria: {
      allOf: [
        {
          // Filters requests table by the FastAPI route name for image generation.
          // operation_Name in App Insights for FastAPI routes is typically:
          //   "POST /sieges/{siege_id}/generate-images"
          // TODO(#246-phase5): confirm exact operation_Name from dev requests table:
          //   requests | where cloud_RoleName == "siege-api" | where name has "generate-images"
          //           | summarize count() by name | order by count_ desc
          query: '''
requests
| where timestamp > ago(5m)
| where cloud_RoleName == "siege-api"
| where name has "generate-images"
| where duration > 10000  // duration is milliseconds in App Insights
| summarize slowRenders = count(), maxMs = max(duration)
| where slowRenders > 0
| project slowRenders, maxMs
'''
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 0
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: [actionGroup.id]
    }
  }
}

// ── Outputs ───────────────────────────────────────────────────────────────────

@description('Resource ID of the deployed action group')
output actionGroupId string = actionGroup.id

@description('Name of the deployed action group')
output actionGroupName string = actionGroup.name
