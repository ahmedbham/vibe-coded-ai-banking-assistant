@description('Azure region for the resources.')
param location string

@description('Name of the AI Hub workspace.')
param hubName string

@description('Name of the AI Project workspace.')
param projectName string

@description('Name of the storage account required by the AI Hub.')
param storageAccountName string

@description('Resource ID of the Key Vault for the AI Hub.')
param keyVaultId string

@description('Resource ID of the Application Insights instance.')
param appInsightsId string

@description('Principal ID of the managed identity to assign Azure AI Developer role.')
param identityPrincipalId string

@description('Environment tag (e.g. dev, prod).')
param environment string

@description('Project tag.')
param project string

@description('Owner tag.')
param owner string

// ---------------------------------------------------------------------------
// Storage account (required by AI Hub)
// ---------------------------------------------------------------------------

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  tags: {
    environment: environment
    project: project
    owner: owner
  }
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
  }
}

// ---------------------------------------------------------------------------
// AI Hub
// ---------------------------------------------------------------------------

resource aiHub 'Microsoft.MachineLearningServices/workspaces@2024-07-01-preview' = {
  name: hubName
  location: location
  kind: 'Hub'
  identity: {
    type: 'SystemAssigned'
  }
  tags: {
    environment: environment
    project: project
    owner: owner
  }
  properties: {
    description: 'AI Hub for banking assistant'
    friendlyName: hubName
    storageAccount: storageAccount.id
    keyVault: keyVaultId
    applicationInsights: appInsightsId
    publicNetworkAccess: 'Enabled'
    managedNetwork: {
      isolationMode: 'Disabled'
    }
  }
}

// ---------------------------------------------------------------------------
// AI Project
// ---------------------------------------------------------------------------

resource aiProject 'Microsoft.MachineLearningServices/workspaces@2024-07-01-preview' = {
  name: projectName
  location: location
  kind: 'Project'
  identity: {
    type: 'SystemAssigned'
  }
  tags: {
    environment: environment
    project: project
    owner: owner
  }
  properties: {
    description: 'AI Project for banking assistant agents'
    friendlyName: projectName
    hubResourceId: aiHub.id
    publicNetworkAccess: 'Enabled'
  }
}

// ---------------------------------------------------------------------------
// Azure AI Developer role assignment on the project
// ---------------------------------------------------------------------------

var azureAIDeveloperRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '64702f94-c441-49e6-a78b-ef80e0188fee'
)

resource aiDeveloperRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiProject.id, identityPrincipalId, azureAIDeveloperRoleDefinitionId)
  scope: aiProject
  properties: {
    roleDefinitionId: azureAIDeveloperRoleDefinitionId
    principalId: identityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

@description('Resource ID of the AI Hub.')
output hubId string = aiHub.id

@description('Resource ID of the AI Project.')
output projectId string = aiProject.id

// Azure ML workspace discoveryUrl is always formatted as
// "https://<workspace>.api.azureml.ms/discovery". Strip the suffix to get
// the base endpoint accepted by the azure-ai-agents SDK. If the URL doesn't
// contain '/discovery', replace() returns it unchanged.
@description('Endpoint of the AI Project for the azure-ai-agents SDK (strips /discovery suffix).')
output projectEndpoint string = replace(aiProject.properties.discoveryUrl, '/discovery', '')
