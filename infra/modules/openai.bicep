@description('Azure region for the resource.')
param location string

@description('Name of the Azure OpenAI account.')
param openAIName string

@description('Name of the GPT-4.1 model deployment.')
param gptDeploymentName string = 'gpt-4.1'

@description('Capacity in thousands of tokens per minute for the GPT-4.1 deployment.')
param gptCapacity int = 10

@description('Principal ID of the managed identity to assign the Cognitive Services OpenAI User role.')
param identityPrincipalId string

@description('Environment tag (e.g. dev, prod).')
param environment string

@description('Project tag.')
param project string

@description('Owner tag.')
param owner string

// ---------------------------------------------------------------------------
// Azure OpenAI account
// ---------------------------------------------------------------------------

resource openAIAccount 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: openAIName
  location: location
  kind: 'OpenAI'
  tags: {
    environment: environment
    project: project
    owner: owner
  }
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: openAIName
    publicNetworkAccess: 'Enabled'
  }
}

// ---------------------------------------------------------------------------
// GPT-4.1 model deployment
// ---------------------------------------------------------------------------

resource gptDeployment 'Microsoft.CognitiveServices/accounts/deployments@2023-05-01' = {
  parent: openAIAccount
  name: gptDeploymentName
  sku: {
    name: 'Standard'
    capacity: gptCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4.1'
      version: '2025-04-14'
    }
    versionUpgradeOption: 'OnceCurrentVersionExpired'
  }
}

// ---------------------------------------------------------------------------
// Cognitive Services OpenAI User role assignment
// ---------------------------------------------------------------------------

var cognitiveServicesOpenAIUserRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
)

resource openAIUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAIAccount.id, identityPrincipalId, cognitiveServicesOpenAIUserRoleDefinitionId)
  scope: openAIAccount
  properties: {
    roleDefinitionId: cognitiveServicesOpenAIUserRoleDefinitionId
    principalId: identityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

@description('Endpoint of the Azure OpenAI account.')
output endpoint string = openAIAccount.properties.endpoint

@description('Resource ID of the Azure OpenAI account.')
output accountId string = openAIAccount.id

@description('Name of the GPT-4.1 model deployment.')
output deploymentName string = gptDeployment.name
