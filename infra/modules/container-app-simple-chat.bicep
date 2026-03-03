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
    'azd-service-name': 'simple-chat'
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
        targetPort: 80
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
          name: 'simple-chat'
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
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
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
