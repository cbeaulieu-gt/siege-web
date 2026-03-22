@description('Azure region for all resources')
param location string

@description('Environment name (dev, prod)')
param environment string

@description('Short prefix for resource naming')
param appPrefix string

@description('PostgreSQL administrator username')
param adminUsername string

@description('PostgreSQL administrator password')
@secure()
param adminPassword string

@description('Enable geo-redundant backup (recommended for prod)')
param geoRedundantBackup bool = false

// SKU tier controls performance and HA eligibility.
// Burstable (B-series) is fine for dev — cheap, shared vCores.
// General Purpose (D-series) is required for production:
//   - Dedicated vCores → consistent query latency
//   - Eligible for zone-redundant high availability
//   - Eligible for read replicas
@description('PostgreSQL SKU name (e.g. Standard_B1ms for dev, Standard_D2ds_v5 for prod)')
param postgresSku string = 'Standard_B1ms'

@description('PostgreSQL SKU tier (Burstable | GeneralPurpose | MemoryOptimized)')
@allowed(['Burstable', 'GeneralPurpose', 'MemoryOptimized'])
param postgresSkuTier string = 'Burstable'

@description('Storage size in GB (32 for dev, 64+ for prod)')
param storageSizeGB int = 32

@description('Backup retention in days (7–35)')
@minValue(7)
@maxValue(35)
param backupRetentionDays int = 7

// High availability mode.
// ZoneRedundant requires GeneralPurpose or MemoryOptimized tier.
// Disabled is acceptable for dev; SameZone is a cheaper HA option without
// cross-zone standby. ZoneRedundant is the gold standard for production.
@description('High availability mode (Disabled | SameZone | ZoneRedundant)')
@allowed(['Disabled', 'SameZone', 'ZoneRedundant'])
param highAvailabilityMode string = 'Disabled'

var serverName = '${appPrefix}-pg-${environment}-${uniqueString(resourceGroup().id)}'

resource postgresServer 'Microsoft.DBforPostgreSQL/flexibleServers@2023-06-01-preview' = {
  name: serverName
  location: location
  tags: {
    project: appPrefix
    environment: environment
  }
  sku: {
    name: postgresSku
    tier: postgresSkuTier
  }
  properties: {
    version: '16'
    administratorLogin: adminUsername
    administratorLoginPassword: adminPassword
    storage: {
      storageSizeGB: storageSizeGB
    }
    backup: {
      backupRetentionDays: backupRetentionDays
      geoRedundantBackup: geoRedundantBackup ? 'Enabled' : 'Disabled'
    }
    highAvailability: {
      mode: highAvailabilityMode
    }
  }
}

resource siegeDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-06-01-preview' = {
  parent: postgresServer
  name: 'siege'
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

// Allow Azure services to connect (Container Apps use Azure-internal egress IPs).
// For a hardened production deployment you could remove this rule and instead
// configure a VNet integration so only Container Apps can reach the server.
resource firewallRuleAzure 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-06-01-preview' = {
  parent: postgresServer
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

output serverId string = postgresServer.id
output serverName string = postgresServer.name
output serverFqdn string = postgresServer.properties.fullyQualifiedDomainName
output databaseName string = siegeDatabase.name
