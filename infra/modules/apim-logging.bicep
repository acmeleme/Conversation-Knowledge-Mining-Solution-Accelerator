// ============================================================
// APIM Logging — Azure Monitor + Application Insights
// Phase 2: Observability for token usage and API performance
// ============================================================

@description('APIM service name')
param apimServiceName string

@description('Application Insights instrumentation key')
param appInsightsInstrumentationKey string

@description('Application Insights resource ID')
param appInsightsResourceId string

@description('Log Analytics workspace ID')
param logAnalyticsWorkspaceId string = ''

// Reference to existing APIM
resource apim 'Microsoft.ApiManagement/service@2023-09-01-preview' existing = {
  name: apimServiceName
}

// ============================================================
// Application Insights Logger
// ============================================================
resource appInsightsLogger 'Microsoft.ApiManagement/service/loggers@2023-09-01-preview' = {
  name: 'applicationinsights'
  parent: apim
  properties: {
    loggerType: 'applicationInsights'
    description: 'Application Insights logger for token usage and API performance tracking'
    credentials: {
      instrumentationKey: appInsightsInstrumentationKey
    }
    isBuffered: true
    resourceId: appInsightsResourceId
  }
}

// ============================================================
// Azure Monitor Logger
// ============================================================
resource azureMonitorLogger 'Microsoft.ApiManagement/service/loggers@2023-09-01-preview' = {
  name: 'azuremonitor'
  parent: apim
  properties: {
    loggerType: 'azureMonitor'
    description: 'Azure Monitor logger for operational metrics'
    isBuffered: false
  }
}

// ============================================================
// Diagnostic settings — log all API calls to Application Insights
// ============================================================
resource apimDiagnostics 'Microsoft.ApiManagement/service/diagnostics@2023-09-01-preview' = {
  name: 'applicationinsights'
  parent: apim
  properties: {
    loggerId: appInsightsLogger.id
    alwaysLog: 'allErrors'
    sampling: {
      samplingType: 'fixed'
      percentage: 100
    }
    request: {
      headers: ['X-User-Id', 'X-APIM-Request-Id', 'Content-Type']
      body: {
        bytes: 512
      }
    }
    response: {
      headers: ['Content-Type', 'X-RateLimit-Remaining', 'X-APIM-Version']
      body: {
        bytes: 512
      }
    }
    logClientIp: true
    verbosity: 'information'
  }
}

// ============================================================
// Outputs
// ============================================================
output appInsightsLoggerId string = appInsightsLogger.id
output azureMonitorLoggerId string = azureMonitorLogger.id
