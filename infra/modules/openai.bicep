@description('Name of the existing Foundry account.')
param foundryName string

@description('Name for the model deployment.')
param modelDeploymentName string = 'agent-model'

@description('Principal ID of the managed identity to assign AI roles.')
param managedIdentityPrincipalId string

@description('Models are managed at the account level. Deploy the GPT model used for agent logic.')
resource foundry 'Microsoft.CognitiveServices/accounts@2025-10-01-preview' existing = {
  name: foundryName

  resource model 'deployments' = {
    name: modelDeploymentName
    sku: {
      capacity: 50
      name: 'GlobalStandard'
    }
    properties: {
      model: {
        format: 'OpenAI'
        name: 'gpt-4p'
        version: '2024-11-20'
      }
      versionUpgradeOption: 'NoAutoUpgrade'
      raiPolicyName: 'Microsoft.DefaultV2'
    }
  }
}

// Cognitive Services User – allows calling Azure Cognitive Services / OpenAI APIs
var cognitiveServicesUserRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'a97b65f3-24c7-4388-baec-2e87135dc908'
)

// Azure AI Developer – allows creating / managing agents in Foundry Agent Service
var azureAiDeveloperRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '64702f94-c441-49e6-a78b-ef80e0188fee'
)

resource openAiUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, managedIdentityPrincipalId, cognitiveServicesUserRoleId)
  scope: foundry
  properties: {
    roleDefinitionId: cognitiveServicesUserRoleId
    principalId: managedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource aiDeveloperRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, managedIdentityPrincipalId, azureAiDeveloperRoleId)
  scope: foundry
  properties: {
    roleDefinitionId: azureAiDeveloperRoleId
    principalId: managedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

@description('Name of the model deployment.')
output modelDeploymentName string = foundry::model.name
