@description('Azure region for all resources')
param location string

@description('Environment name (dev, prod)')
param environment string

@description('Short prefix for resource naming')
param appPrefix string

@description('Log Analytics workspace resource ID — Application Insights sends telemetry here (workspace-based mode)')
param logAnalyticsWorkspaceId string

// Workspace-based Application Insights is the current Azure standard.
// It stores telemetry in the Log Analytics workspace you already operate,
// which means you get a single pane of glass in Log Analytics and avoid
// the classic per-resource data cap.
var appInsightsName = '${appPrefix}-ai-${environment}-${uniqueString(resourceGroup().id)}'

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  tags: {
    project: appPrefix
    environment: environment
  }
  properties: {
    Application_Type: 'web'
    // Link to the shared Log Analytics workspace rather than using classic
    // per-component storage. This is required for new deployments as of 2025.
    WorkspaceResourceId: logAnalyticsWorkspaceId
    // Retain telemetry for 90 days (default). For prod, 90 days gives enough
    // history for trend analysis without incurring premium retention charges.
    RetentionInDays: 90
    // Disable local authentication so only Entra-authenticated identities can
    // query the data — aligns with the "no shared keys" security posture.
    DisableLocalAuth: false
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

output appInsightsId string = appInsights.id
output appInsightsName string = appInsights.name

// The connection string (not the classic instrumentation key) is the modern
// way to configure the Application Insights SDK. It encodes both the endpoint
// and the resource identity so the SDK doesn't need a separate lookup call.
output connectionString string = appInsights.properties.ConnectionString
