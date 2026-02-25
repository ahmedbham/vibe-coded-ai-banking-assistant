@description('Azure region for all resources.')
param location string

@description('Name of the Microsoft Foundry Hub workspace.')
param foundryHubName string

@description('Name of the Microsoft Foundry Project workspace.')
param foundryProjectName string

@description('Name of the Azure AI Services account.')
param aiServicesName string

@description('Name of the storage account used by the Foundry Hub.')
param storageAccountName string

@description('Resource ID of the existing Azure Key Vault.')
param keyVaultId string

@description('Resource ID of the existing Application Insights instance.')
param appInsightsId string

@description('Principal ID of the managed identity to assign roles.')
param identityPrincipalId string

@description('Environment tag (e.g. dev, prod).')
param environment string

@description('Project tag.')
param project string

@description('Owner tag.')
param owner string

// ---------------------------------------------------------------------------
// Storage account required by the Foundry Hub
// ---------------------------------------------------------------------------

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
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
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
  }
}

// ---------------------------------------------------------------------------
// Azure AI Services account (provides OpenAI & other AI APIs for the Hub)
// ---------------------------------------------------------------------------

resource aiServices 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: aiServicesName
  location: location
  tags: {
    environment: environment
    project: project
    owner: owner
  }
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: aiServicesName
    publicNetworkAccess: 'Enabled'
  }
}

// ---------------------------------------------------------------------------
// Microsoft Foundry Hub
// ---------------------------------------------------------------------------

resource foundryHub 'Microsoft.MachineLearningServices/workspaces@2024-10-01' = {
  name: foundryHubName
  location: location
  tags: {
    environment: environment
    project: project
    owner: owner
  }
  kind: 'Hub'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    friendlyName: foundryHubName
    storageAccount: storage.id
    keyVault: keyVaultId
    applicationInsights: appInsightsId
  }
}

// ---------------------------------------------------------------------------
// AI Services connection inside the Hub
// ---------------------------------------------------------------------------

resource aiServicesConnection 'Microsoft.MachineLearningServices/workspaces/connections@2024-10-01' = {
  parent: foundryHub
  name: '${foundryHubName}-aiservices'
  properties: {
    category: 'AIServices'
    target: aiServices.properties.endpoint
    authType: 'AAD'
    metadata: {
      ApiVersion: '2024-05-01-preview'
      ApiType: 'Azure'
      ResourceId: aiServices.id
    }
  }
}

// ---------------------------------------------------------------------------
// Microsoft Foundry Project
// ---------------------------------------------------------------------------

resource foundryProject 'Microsoft.MachineLearningServices/workspaces@2024-10-01' = {
  name: foundryProjectName
  location: location
  tags: {
    environment: environment
    project: project
    owner: owner
  }
  kind: 'Project'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    friendlyName: foundryProjectName
    hubResourceId: foundryHub.id
  }
}

// ---------------------------------------------------------------------------
// Role assignments for the managed identity
// ---------------------------------------------------------------------------

// Cognitive Services OpenAI User – allows the identity to call OpenAI APIs
var cognitiveServicesOpenAiUserRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
)

resource openAiUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiServices.id, identityPrincipalId, cognitiveServicesOpenAiUserRoleId)
  scope: aiServices
  properties: {
    roleDefinitionId: cognitiveServicesOpenAiUserRoleId
    principalId: identityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Azure AI Developer – allows the identity to interact with Foundry Agent Service
var azureAiDeveloperRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '64702f94-c441-49e6-a78b-ef80e0188fee'
)

resource aiDeveloperRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundryProject.id, identityPrincipalId, azureAiDeveloperRoleId)
  scope: foundryProject
  properties: {
    roleDefinitionId: azureAiDeveloperRoleId
    principalId: identityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

@description('Resource ID of the Foundry Hub workspace.')
output hubId string = foundryHub.id

@description('Resource ID of the Foundry Project workspace.')
output projectId string = foundryProject.id

@description('Name of the Azure AI Services account.')
output aiServicesName string = aiServices.name

@description('Endpoint URL of the Azure AI Services account.')
output aiServicesEndpoint string = aiServices.properties.endpoint

@description('Discovery URL of the Foundry Project (used by MAF agents).')
output foundryProjectEndpoint string = foundryProject.properties.discoveryUrl
