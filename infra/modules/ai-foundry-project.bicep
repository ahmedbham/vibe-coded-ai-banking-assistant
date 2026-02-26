@description('Azure region for the resource.')
param location string

@description('Name of the existing Foundry account.')
param foundryName string

@description('Name for the Foundry project.')
param projectName string

@description('Resource ID of the user-assigned managed identity for the project identity.')
param managedIdentityId string

@description('Environment tag (e.g. dev, prod).')
param environment string

@description('Project tag.')
param project string

@description('Owner tag.')
param owner string

@description('Existing Foundry account. The project is created as a child resource of this account.')
resource foundry 'Microsoft.CognitiveServices/accounts@2025-10-01-preview' existing = {
  name: foundryName

  resource foundryProject 'projects' = {
    name: projectName
    location: location
    identity: {
      type: 'UserAssigned'
      userAssignedIdentities: {
        '${managedIdentityId}': {}
      }
    }
    tags: {
      environment: environment
      project: project
      owner: owner
    }
    properties: {
      description: 'Banking assistant multi-agent project'
      displayName: 'Banking Assistant'
    }
  }
}

@description('Resource ID of the Foundry project.')
output id string = foundry::foundryProject.id

@description('Name of the Foundry project.')
output name string = foundry::foundryProject.name

@description('Endpoint of the Foundry project.')
output projectEndpoint string = foundry::foundryProject.properties.endpoints['AI Foundry API']
