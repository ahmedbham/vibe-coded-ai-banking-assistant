@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Short environment name (e.g. dev, prod).')
@allowed(['dev', 'staging', 'prod'])
param environment string = 'dev'

@description('Short project identifier used in resource names.')
param project string = 'banking'

@description('Owner tag applied to every resource.')
param owner string = 'platform-team'

// ---------------------------------------------------------------------------
// Derived naming
// ---------------------------------------------------------------------------
var suffix = '${project}-${environment}'

// 6-char deterministic suffix unique to this resource group, ensuring
// globally-unique names for Key Vault (max 24 chars) and ACR (max 50 chars).
var uniqueSuffix = take(uniqueString(resourceGroup().id), 6)

var identityName         = 'id-${suffix}'
var workspaceName        = 'log-${suffix}'
var appInsightsName      = 'appi-${suffix}'
var registryName         = replace('acr${suffix}${uniqueSuffix}', '-', '')
var keyVaultName         = 'kv-${suffix}-${uniqueSuffix}'
var containerAppsEnvName = 'cae-${suffix}'
var accountServiceAppName = 'ca-account-${suffix}'
var transactionsServiceAppName = 'ca-transactions-${suffix}'
var paymentsServiceAppName = 'ca-payments-${suffix}'
var accountMcpAppName = 'ca-account-mcp-${suffix}'
var transactionsMcpAppName = 'ca-transactions-mcp-${suffix}'
var paymentsMcpAppName = 'ca-payments-mcp-${suffix}'
var aiHubName            = 'aih-${suffix}'
var aiProjectName        = 'aip-${suffix}'
var aiStorageName        = 'st${replace(suffix, '-', '')}${uniqueSuffix}'
var openAIName           = 'oai-${suffix}-${uniqueSuffix}'
var gptDeploymentName    = 'gpt-4.1'

// ---------------------------------------------------------------------------
// Modules
// ---------------------------------------------------------------------------

module identity 'modules/managed-identity.bicep' = {
  name: 'deploy-identity'
  params: {
    location: location
    identityName: identityName
    environment: environment
    project: project
    owner: owner
  }
}

module monitor 'modules/monitor.bicep' = {
  name: 'deploy-monitor'
  params: {
    location: location
    workspaceName: workspaceName
    appInsightsName: appInsightsName
    environment: environment
    project: project
    owner: owner
  }
}

module containerRegistry 'modules/container-registry.bicep' = {
  name: 'deploy-acr'
  params: {
    location: location
    registryName: registryName
    acrPullPrincipalId: identity.outputs.principalId
    environment: environment
    project: project
    owner: owner
  }
}

module keyVault 'modules/key-vault.bicep' = {
  name: 'deploy-keyvault'
  params: {
    location: location
    keyVaultName: keyVaultName
    identityPrincipalId: identity.outputs.principalId
    environment: environment
    project: project
    owner: owner
  }
}

module containerAppsEnv 'modules/container-apps-env.bicep' = {
  name: 'deploy-container-apps-env'
  params: {
    location: location
    envName: containerAppsEnvName
    logAnalyticsWorkspaceId: monitor.outputs.workspaceId
    environment: environment
    project: project
    owner: owner
  }
}

module accountServiceApp 'modules/container-app-account-service.bicep' = {
  name: 'deploy-account-service'
  params: {
    location: location
    containerAppName: accountServiceAppName
    containerAppsEnvId: containerAppsEnv.outputs.id
    acrLoginServer: containerRegistry.outputs.loginServer
    managedIdentityId: identity.outputs.id
    managedIdentityClientId: identity.outputs.clientId
    appInsightsConnectionString: monitor.outputs.appInsightsConnectionString
    environment: environment
    project: project
    owner: owner
  }
}

module transactionsServiceApp 'modules/container-app-transactions-service.bicep' = {
  name: 'deploy-transactions-service'
  params: {
    location: location
    containerAppName: transactionsServiceAppName
    containerAppsEnvId: containerAppsEnv.outputs.id
    acrLoginServer: containerRegistry.outputs.loginServer
    managedIdentityId: identity.outputs.id
    managedIdentityClientId: identity.outputs.clientId
    appInsightsConnectionString: monitor.outputs.appInsightsConnectionString
    environment: environment
    project: project
    owner: owner
  }
}

module paymentsServiceApp 'modules/container-app-payments-service.bicep' = {
  name: 'deploy-payments-service'
  params: {
    location: location
    containerAppName: paymentsServiceAppName
    containerAppsEnvId: containerAppsEnv.outputs.id
    acrLoginServer: containerRegistry.outputs.loginServer
    managedIdentityId: identity.outputs.id
    managedIdentityClientId: identity.outputs.clientId
    appInsightsConnectionString: monitor.outputs.appInsightsConnectionString
    environment: environment
    project: project
    owner: owner
  }
}

module accountMcpApp 'modules/container-app-account-mcp.bicep' = {
  name: 'deploy-account-mcp'
  params: {
    location: location
    containerAppName: accountMcpAppName
    containerAppsEnvId: containerAppsEnv.outputs.id
    acrLoginServer: containerRegistry.outputs.loginServer
    managedIdentityId: identity.outputs.id
    managedIdentityClientId: identity.outputs.clientId
    appInsightsConnectionString: monitor.outputs.appInsightsConnectionString
    accountServiceUrl: 'https://${accountServiceApp.outputs.fqdn}'
    environment: environment
    project: project
    owner: owner
  }
}

module transactionsMcpApp 'modules/container-app-transactions-mcp.bicep' = {
  name: 'deploy-transactions-mcp'
  params: {
    location: location
    containerAppName: transactionsMcpAppName
    containerAppsEnvId: containerAppsEnv.outputs.id
    acrLoginServer: containerRegistry.outputs.loginServer
    managedIdentityId: identity.outputs.id
    managedIdentityClientId: identity.outputs.clientId
    appInsightsConnectionString: monitor.outputs.appInsightsConnectionString
    transactionsServiceUrl: 'https://${transactionsServiceApp.outputs.fqdn}'
    environment: environment
    project: project
    owner: owner
  }
}

module paymentsMcpApp 'modules/container-app-payments-mcp.bicep' = {
  name: 'deploy-payments-mcp'
  params: {
    location: location
    containerAppName: paymentsMcpAppName
    containerAppsEnvId: containerAppsEnv.outputs.id
    acrLoginServer: containerRegistry.outputs.loginServer
    managedIdentityId: identity.outputs.id
    managedIdentityClientId: identity.outputs.clientId
    appInsightsConnectionString: monitor.outputs.appInsightsConnectionString
    paymentsServiceUrl: 'https://${paymentsServiceApp.outputs.fqdn}'
    environment: environment
    project: project
    owner: owner
  }
}

module aiFoundry 'modules/ai-foundry.bicep' = {
  name: 'deploy-ai-foundry'
  params: {
    location: location
    hubName: aiHubName
    projectName: aiProjectName
    storageAccountName: aiStorageName
    keyVaultId: keyVault.outputs.id
    appInsightsId: resourceId('Microsoft.Insights/components', appInsightsName)
    identityPrincipalId: identity.outputs.principalId
    environment: environment
    project: project
    owner: owner
  }
  dependsOn: [
    monitor
  ]
}

module openAI 'modules/openai.bicep' = {
  name: 'deploy-openai'
  params: {
    location: location
    openAIName: openAIName
    gptDeploymentName: gptDeploymentName
    identityPrincipalId: identity.outputs.principalId
    environment: environment
    project: project
    owner: owner
  }
}

// ---------------------------------------------------------------------------
// Outputs – human-readable
// ---------------------------------------------------------------------------

@description('Login server of the Azure Container Registry.')
output acrLoginServer string = containerRegistry.outputs.loginServer

@description('URI of the Azure Key Vault.')
output keyVaultUri string = keyVault.outputs.uri

@description('Application Insights connection string.')
output appInsightsConnectionString string = monitor.outputs.appInsightsConnectionString

@description('Container Apps environment default domain.')
output containerAppsEnvDomain string = containerAppsEnv.outputs.defaultDomain

@description('Client ID of the user-assigned managed identity.')
output managedIdentityClientId string = identity.outputs.clientId

// ---------------------------------------------------------------------------
// Outputs – azd conventions (uppercase = auto-mapped to azd environment vars)
// ---------------------------------------------------------------------------

@description('ACR login server for azd image push.')
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.outputs.loginServer

@description('Container Apps managed environment name for azd service deployment.')
output AZURE_CONTAINER_APPS_ENVIRONMENT_NAME string = containerAppsEnvName

@description('Key Vault URI consumed by azd-deployed services.')
output AZURE_KEY_VAULT_ENDPOINT string = keyVault.outputs.uri

@description('Application Insights connection string for azd-deployed services.')
output APPLICATIONINSIGHTS_CONNECTION_STRING string = monitor.outputs.appInsightsConnectionString

@description('Client ID of the managed identity for azd-deployed services.')
output AZURE_CLIENT_ID string = identity.outputs.clientId

@description('FQDN of the Account Service Container App.')
output accountServiceFqdn string = accountServiceApp.outputs.fqdn

@description('FQDN of the Transactions Service Container App.')
output transactionsServiceFqdn string = transactionsServiceApp.outputs.fqdn

@description('FQDN of the Payments Service Container App.')
output paymentsServiceFqdn string = paymentsServiceApp.outputs.fqdn

@description('FQDN of the Account MCP Container App.')
output accountMcpFqdn string = accountMcpApp.outputs.fqdn

@description('FQDN of the Transactions MCP Container App.')
output transactionsMcpFqdn string = transactionsMcpApp.outputs.fqdn

@description('FQDN of the Payments MCP Container App.')
output paymentsMcpFqdn string = paymentsMcpApp.outputs.fqdn

// ---------------------------------------------------------------------------
// Outputs – Microsoft Foundry & Azure OpenAI
// ---------------------------------------------------------------------------

@description('Endpoint of the AI Project for agents (FOUNDRY_PROJECT_ENDPOINT).')
output foundryProjectEndpoint string = aiFoundry.outputs.projectEndpoint

@description('Endpoint of the Azure OpenAI account (AZURE_OPENAI_ENDPOINT).')
output openAIEndpoint string = openAI.outputs.endpoint

@description('Name of the GPT-4.1 model deployment.')
output gptDeploymentName string = openAI.outputs.deploymentName

// azd-convention outputs (uppercase = auto-mapped to azd environment vars)

@description('AI Project endpoint for azd-deployed agent services.')
output FOUNDRY_PROJECT_ENDPOINT string = aiFoundry.outputs.projectEndpoint

@description('Azure OpenAI endpoint for azd-deployed agent services.')
output AZURE_OPENAI_ENDPOINT string = openAI.outputs.endpoint

@description('GPT-4.1 deployment name for azd-deployed agent services.')
output FOUNDRY_MODEL_DEPLOYMENT_NAME string = openAI.outputs.deploymentName
