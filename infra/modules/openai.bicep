@description('Name of the existing Azure AI Services account to deploy the model into.')
param aiServicesAccountName string

@description('Name of the GPT-4.1 model deployment.')
param deploymentName string = 'gpt-4-1'

@description('Tokens-per-minute capacity (in thousands) for the deployment.')
param capacityK int = 10

// ---------------------------------------------------------------------------
// Reference the existing AI Services account created by ai-foundry.bicep
// ---------------------------------------------------------------------------

resource aiServicesAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: aiServicesAccountName
}

// ---------------------------------------------------------------------------
// GPT-4.1 model deployment
// ---------------------------------------------------------------------------

resource gpt41Deployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: aiServicesAccount
  name: deploymentName
  sku: {
    name: 'GlobalStandard'
    capacity: capacityK
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4.1'
      version: '2025-04-14'
    }
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

@description('Name of the GPT-4.1 model deployment.')
output deploymentName string = gpt41Deployment.name

@description('Azure OpenAI endpoint inherited from the AI Services account.')
output endpoint string = aiServicesAccount.properties.endpoint
