// ── cert-identity.bicep ───────────────────────────────────────────────────────
//
// Creates a user-assigned managed identity (UAMI) for the Container Apps
// environment to use when importing a BYO certificate from Key Vault.
//
// WHY a user-assigned identity instead of system-assigned?
// The Container Apps environment's system-assigned identity is only available
// after the environment is created, which means we cannot create a role
// assignment for it in the same Bicep deployment without a circular dependency.
// A user-assigned identity exists before the environment is created, so the
// role assignment can be declared in the same pass.
//
// WHY a separate module for this?
// The same BCP120 reason that drove kv-role-assignments.bicep: the Key Vault
// name is a runtime output in main.bicep, so `existing` references on it are
// only valid inside a module that receives the name as a plain string parameter.
//
// Role granted: Key Vault Secrets User (4633458b-17de-408a-b874-0445c86b69e6)
// Microsoft Learn confirms this is the correct role for the Container Apps
// environment identity to read/import a certificate stored in Key Vault.
// See: https://learn.microsoft.com/azure/container-apps/key-vault-certificates-manage

@description('Azure region for all resources')
param location string

@description('Environment name (dev, prod)')
param environment string

@description('Short prefix for resource naming')
param appPrefix string

@description('Name of the existing Key Vault where the origin cert PFX will be stored')
param vaultName string

// ── User-assigned managed identity ───────────────────────────────────────────

resource certIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${appPrefix}-cert-uami-${environment}'
  location: location
  tags: {
    project: appPrefix
    environment: environment
    purpose: 'container-apps-cert-import'
  }
}

// ── Key Vault Secrets User role assignment ────────────────────────────────────
//
// The Container Apps environment uses this identity when calling Key Vault to
// retrieve the PFX bytes for the certificate import. "Key Vault Secrets User"
// (read secret value) is sufficient — Key Vault stores the PFX as a secret
// behind the scenes even though it is modelled as a certificate object.

var kvSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: vaultName
}

resource kvRoleCertIdentity 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  // guid() with three unique seeds produces a stable, idempotent role-assignment
  // name — re-running the deployment never creates a duplicate assignment.
  name: guid(keyVault.id, certIdentity.id, kvSecretsUserRoleId)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvSecretsUserRoleId)
    principalId: certIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ── Outputs ──────────────────────────────────────────────────────────────────

output identityId string = certIdentity.id
output identityClientId string = certIdentity.properties.clientId
output identityPrincipalId string = certIdentity.properties.principalId
