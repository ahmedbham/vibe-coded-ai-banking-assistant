@description('Azure region for the resource.')
param location string

@description('Name of the Azure Container Registry.')
param registryName string

@description('SKU for the container registry.')
@allowed(['Basic', 'Standard', 'Premium'])
param sku string = 'Basic'

@description('Principal ID to assign the AcrPull role.')
param acrPullPrincipalId string

@description('Environment tag (e.g. dev, prod).')
param environment string

@description('Project tag.')
param project string

@description('Owner tag.')
param owner string

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: registryName
  location: location
  tags: {
    environment: environment
    project: project
    owner: owner
  }
  sku: {
    name: sku
  }
  properties: {
    adminUserEnabled: false
  }
}

// AcrPull built-in role definition ID
var acrPullRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')

resource acrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerRegistry.id, acrPullPrincipalId, acrPullRoleDefinitionId)
  scope: containerRegistry
  properties: {
    roleDefinitionId: acrPullRoleDefinitionId
    principalId: acrPullPrincipalId
    principalType: 'ServicePrincipal'
  }
}

@description('Login server of the Azure Container Registry.')
output loginServer string = containerRegistry.properties.loginServer

@description('Resource ID of the Azure Container Registry.')
output id string = containerRegistry.id
