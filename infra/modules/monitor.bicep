@description('Azure region for the resources.')
param location string

@description('Name of the Log Analytics workspace.')
param workspaceName string

@description('Name of the Application Insights instance.')
param appInsightsName string

@description('Environment tag (e.g. dev, prod).')
param environment string

@description('Project tag.')
param project string

@description('Owner tag.')
param owner string

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: workspaceName
  location: location
  tags: {
    environment: environment
    project: project
    owner: owner
  }
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  tags: {
    environment: environment
    project: project
    owner: owner
  }
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalyticsWorkspace.id
  }
}

@description('Resource ID of the Log Analytics workspace.')
output workspaceId string = logAnalyticsWorkspace.id

@description('Instrumentation key of the Application Insights instance.')
output appInsightsInstrumentationKey string = appInsights.properties.InstrumentationKey

@description('Connection string of the Application Insights instance.')
output appInsightsConnectionString string = appInsights.properties.ConnectionString
