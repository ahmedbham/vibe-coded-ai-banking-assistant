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

var identityName        = 'id-${suffix}'
var workspaceName       = 'log-${suffix}'
var appInsightsName     = 'appi-${suffix}'
var registryName        = replace('acr${suffix}', '-', '')
var keyVaultName        = 'kv-${suffix}'
var containerAppsEnvName = 'cae-${suffix}'

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

// ---------------------------------------------------------------------------
// Outputs
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
