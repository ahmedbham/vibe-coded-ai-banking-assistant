@description('Azure region for the resource.')
param location string

@description('Name of the Azure Key Vault.')
param keyVaultName string

@description('Principal ID of the managed identity to assign the Key Vault Secrets User role.')
param identityPrincipalId string

@description('Environment tag (e.g. dev, prod).')
param environment string

@description('Project tag.')
param project string

@description('Owner tag.')
param owner string

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: {
    environment: environment
    project: project
    owner: owner
  }
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
  }
}

// Key Vault Secrets User built-in role definition ID
var keyVaultSecretsUserRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')

resource kvSecretsUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, identityPrincipalId, keyVaultSecretsUserRoleDefinitionId)
  scope: keyVault
  properties: {
    roleDefinitionId: keyVaultSecretsUserRoleDefinitionId
    principalId: identityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

@description('URI of the Azure Key Vault.')
output uri string = keyVault.properties.vaultUri

@description('Resource ID of the Azure Key Vault.')
output id string = keyVault.id
