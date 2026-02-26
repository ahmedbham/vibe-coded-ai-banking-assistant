@description('Azure region for the resource.')
param location string

@description('Name of the Foundry account (must be globally unique).')
param foundryName string

@description('Environment tag (e.g. dev, prod).')
param environment string

@description('Project tag.')
param project string

@description('Owner tag.')
param owner string

@description('Deploy Microsoft Foundry (account) with Foundry Agent Service capability.')
resource foundry 'Microsoft.CognitiveServices/accounts@2025-10-01-preview' = {
  name: foundryName
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  tags: {
    environment: environment
    project: project
    owner: owner
  }
  properties: {
    customSubDomainName: foundryName
    allowProjectManagement: true
  }
}

@description('Resource ID of the Foundry account.')
output id string = foundry.id

@description('Name of the Foundry account.')
output name string = foundry.name

@description('Endpoint of the Foundry account.')
output endpoint string = foundry.properties.endpoint
