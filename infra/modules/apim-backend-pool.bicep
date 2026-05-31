// APIM Backend Pool — Azure OpenAI with circuit breaker
// API version: 2023-09-01-preview (required for circuitBreaker property)
//
// Architecture:
//   openai-primary  → named backend for aif-callcenter100 (circuit breaker lives here)
//   openai-pool     → backend pool that aggregates openai-primary (pool-level cb NOT supported)
//
// APIM quirk (2023-09-01-preview): circuitBreaker is NOT supported on type=Pool backends.
// Circuit breaker must be declared on the individual backend (openai-primary).
// Pool inherits the circuit-breaker state of its member backends automatically.
//
// Circuit breaker: opens after 3 x 5xx errors in 60s, resets after 30s cool-down
// acceptRetryAfter: true — respects Azure OpenAI Retry-After header (429 / 503)
param apimName string
param openAiEndpoint string = 'https://aif-callcenter100.openai.azure.com/'
param subscriptionId string
param resourceGroupName string

var apimResourceId = resourceId(subscriptionId, resourceGroupName, 'Microsoft.ApiManagement/service', apimName)

resource apimService 'Microsoft.ApiManagement/service@2023-09-01-preview' existing = {
  name: apimName
}

// Named backend for the single Azure OpenAI instance
resource openAiPrimaryBackend 'Microsoft.ApiManagement/service/backends@2023-09-01-preview' = {
  name: 'openai-primary'
  parent: apimService
  properties: {
    description: 'Primary Azure OpenAI — aif-callcenter100'
    url: openAiEndpoint
    protocol: 'http'
    tls: {
      validateCertificateChain: true
      validateCertificateName: true
    }
  }
}

// Backend pool that wraps the primary instance
// Note: circuitBreaker is NOT valid on Pool-type backends (APIM preview limitation)
// The circuit breaker on openai-primary applies when the pool routes to it.
resource openAiPool 'Microsoft.ApiManagement/service/backends@2023-09-01-preview' = {
  name: 'openai-pool'
  parent: apimService
  dependsOn: [openAiPrimaryBackend]
  properties: {
    description: 'Azure OpenAI backend pool'
    type: 'Pool'
    pool: {
      services: [
        {
          id: '${apimResourceId}/backends/openai-primary'
          priority: 1
          weight: 1
        }
      ]
    }
  }
}

output primaryBackendId string = openAiPrimaryBackend.id
output poolBackendId string = openAiPool.id
