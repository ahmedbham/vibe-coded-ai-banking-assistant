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
