@description('Azure region for the resource.')
param location string

@description('Name of the user-assigned managed identity.')
param identityName string

@description('Environment tag (e.g. dev, prod).')
param environment string

@description('Project tag.')
param project string

@description('Owner tag.')
param owner string

resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
  tags: {
    environment: environment
    project: project
    owner: owner
  }
}

@description('Resource ID of the managed identity.')
output id string = managedIdentity.id

@description('Client ID of the managed identity.')
output clientId string = managedIdentity.properties.clientId

@description('Principal ID of the managed identity.')
output principalId string = managedIdentity.properties.principalId
