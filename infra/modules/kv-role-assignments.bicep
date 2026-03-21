@description('Name of the existing Key Vault')
param vaultName string

@description('Principal ID of the API Container App managed identity')
param apiPrincipalId string

@description('Principal ID of the Frontend Container App managed identity')
param frontendPrincipalId string

@description('Principal ID of the Bot Container App managed identity')
param botPrincipalId string

// Built-in "Key Vault Secrets User" role definition ID (read-only secret access)
var kvSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'

// Resolving `existing` from a plain string parameter is valid at compile time —
// this is why role assignments must live in their own module rather than in
// main.bicep, where the vault name would be a runtime module output (BCP120).
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: vaultName
}

resource kvRoleApi 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, apiPrincipalId, kvSecretsUserRoleId)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvSecretsUserRoleId)
    principalId: apiPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource kvRoleFrontend 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, frontendPrincipalId, kvSecretsUserRoleId)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvSecretsUserRoleId)
    principalId: frontendPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource kvRoleBot 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, botPrincipalId, kvSecretsUserRoleId)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvSecretsUserRoleId)
    principalId: botPrincipalId
    principalType: 'ServicePrincipal'
  }
}
