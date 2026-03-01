@description('Azure region for the resource.')
param location string

@description('Name of the Container App.')
param containerAppName string

@description('Resource ID of the Container Apps managed environment.')
param containerAppsEnvId string

@description('Login server of the Azure Container Registry.')
param acrLoginServer string

@description('Resource ID of the user-assigned managed identity.')
param managedIdentityId string

@description('Client ID of the user-assigned managed identity.')
param managedIdentityClientId string

@description('Application Insights connection string.')
param appInsightsConnectionString string

@description('Azure OpenAI endpoint (Foundry account endpoint).')
param azureOpenAiEndpoint string

@description('Model deployment name.')
param modelDeploymentName string

@description('URL of the Account MCP server (e.g. https://<fqdn>/mcp).')
param accountMcpUrl string

@description('URL of the Transactions MCP server (e.g. https://<fqdn>/mcp).')
param transactionsMcpUrl string

@description('URL of the Payments MCP server (e.g. https://<fqdn>/mcp).')
param paymentsMcpUrl string

@description('Environment tag (e.g. dev, prod).')
param environment string

@description('Project tag.')
param project string

@description('Owner tag.')
param owner string

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppName
  location: location
  tags: {
    environment: environment
    project: project
    owner: owner
    'azd-service-name': 'chat-api'
  }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentityId}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvId
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
      }
      registries: [
        {
          server: acrLoginServer
          identity: managedIdentityId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'chat-api'
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          env: [
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: appInsightsConnectionString
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: managedIdentityClientId
            }
            {
              name: 'AZURE_OPENAI_ENDPOINT'
              value: azureOpenAiEndpoint
            }
            {
              name: 'FOUNDRY_MODEL_DEPLOYMENT_NAME'
              value: modelDeploymentName
            }
            {
              name: 'ACCOUNT_MCP_URL'
              value: accountMcpUrl
            }
            {
              name: 'TRANSACTIONS_MCP_URL'
              value: transactionsMcpUrl
            }
            {
              name: 'PAYMENTS_MCP_URL'
              value: paymentsMcpUrl
            }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 3
      }
    }
  }
}

@description('Fully qualified domain name of the Container App ingress.')
output fqdn string = containerApp.properties.configuration.ingress.fqdn

@description('Resource ID of the Container App.')
output id string = containerApp.id
