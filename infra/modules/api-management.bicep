// ============================================================
// Azure API Management — AI Gateway Module
// Phase 1: Basic APIM setup with OpenAI + AI Foundry backends
// ============================================================

@description('Resource name prefix (e.g., km-financeiro)')
param resourceName string

@description('Azure region for APIM deployment')
param location string = resourceGroup().location

@description('APIM SKU — Developer (no SLA) or Standard/Premium (SLA)')
@allowed(['Developer', 'Standard', 'Premium'])
param apimSku string = 'Developer'

@description('Publisher email for APIM notifications')
param publisherEmail string

@description('Publisher organization name')
param publisherName string = 'Conversation Knowledge Mining'

@description('Azure OpenAI resource endpoint (e.g., https://<resource>.openai.azure.com)')
param azureOpenAiEndpoint string

@description('Azure OpenAI resource ID for RBAC assignment')
param azureOpenAiResourceId string

@description('AI Foundry Agent endpoint (AZURE_AI_AGENT_ENDPOINT value)')
param aiFoundryEndpoint string

// ============================================================
// User-Assigned Managed Identity for APIM
// ============================================================
resource apimIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-apim-${resourceName}'
  location: location
}

// ============================================================
// API Management Service
// ============================================================
resource apim 'Microsoft.ApiManagement/service@2023-09-01-preview' = {
  name: 'apim-${resourceName}'
  location: location
  sku: {
    name: apimSku
    capacity: 1
  }
  identity: {
    type: 'SystemAssigned, UserAssigned'
    userAssignedIdentities: {
      '${apimIdentity.id}': {}
    }
  }
  properties: {
    publisherEmail: publisherEmail
    publisherName: publisherName
    customProperties: {
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Protocols.Tls10': 'False'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Protocols.Tls11': 'False'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Backend.Protocols.Tls10': 'False'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Backend.Protocols.Tls11': 'False'
    }
  }
}

// ============================================================
// APIM Product — "AI Gateway"
// ============================================================
resource aiGatewayProduct 'Microsoft.ApiManagement/service/products@2023-09-01-preview' = {
  name: 'ai-gateway'
  parent: apim
  properties: {
    displayName: 'AI Gateway'
    description: 'Conversation Knowledge Mining — AI Gateway product. Controls access to Azure OpenAI and AI Foundry endpoints.'
    state: 'published'
    subscriptionRequired: true
    approvalRequired: false
    subscriptionsLimit: 100
  }
}

// ============================================================
// Named Values (configuration)
// ============================================================
resource openAiEndpointValue 'Microsoft.ApiManagement/service/namedValues@2023-09-01-preview' = {
  name: 'azure-openai-endpoint'
  parent: apim
  properties: {
    displayName: 'azure-openai-endpoint'
    value: azureOpenAiEndpoint
    secret: false
  }
}

resource aiFoundryEndpointValue 'Microsoft.ApiManagement/service/namedValues@2023-09-01-preview' = {
  name: 'ai-foundry-endpoint'
  parent: apim
  properties: {
    displayName: 'ai-foundry-endpoint'
    value: aiFoundryEndpoint
    secret: false
  }
}

// ============================================================
// Backends
// ============================================================
resource openAiBackend 'Microsoft.ApiManagement/service/backends@2023-09-01-preview' = {
  name: 'azure-openai'
  parent: apim
  properties: {
    description: 'Azure OpenAI Service — primary endpoint for chart generation'
    url: azureOpenAiEndpoint
    protocol: 'http'
    tls: {
      validateCertificateChain: true
      validateCertificateName: true
    }
  }
}

resource aiFoundryBackend 'Microsoft.ApiManagement/service/backends@2023-09-01-preview' = {
  name: 'ai-foundry'
  parent: apim
  properties: {
    description: 'Azure AI Foundry Agent endpoint — primary endpoint for chat (streaming)'
    url: aiFoundryEndpoint
    protocol: 'http'
    tls: {
      validateCertificateChain: true
      validateCertificateName: true
    }
  }
}

// ============================================================
// Global Policy — request ID injection + global rate limit
// Note: MSI auth is applied at individual API-level policies, not globally.
// Using explicit <on-error></on-error> (not self-closing) to avoid APIM
// injecting an implicit <base/> which is invalid in global context.
// ============================================================
resource globalPolicy 'Microsoft.ApiManagement/service/policies@2023-09-01-preview' = {
  name: 'policy'
  parent: apim
  properties: {
    format: 'rawxml'
    value: '''<policies>
  <inbound>
    <rate-limit-by-key calls="1000" renewal-period="60"
      counter-key="@(context.Subscription?.Id ?? &quot;anonymous&quot;)"
      remaining-calls-header-name="X-RateLimit-Remaining"
      retry-after-header-name="Retry-After" />
    <set-header name="X-APIM-Request-Id" exists-action="override">
      <value>@(context.RequestId.ToString())</value>
    </set-header>
  </inbound>
  <backend>
    <forward-request timeout="60" follow-redirects="true" />
  </backend>
  <outbound>
    <set-header name="X-APIM-Version" exists-action="override">
      <value>1.0</value>
    </set-header>
  </outbound>
  <on-error></on-error>
</policies>'''
  }
}

// ============================================================
// RBAC: APIM Managed Identity → Cognitive Services OpenAI User
// ============================================================
var cognitiveServicesOpenAiUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

resource openAiResource 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: last(split(azureOpenAiResourceId, '/'))
}

resource apimOpenAiRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(azureOpenAiResourceId, apim.id, cognitiveServicesOpenAiUserRoleId)
  scope: openAiResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAiUserRoleId)
    principalId: apim.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// ============================================================
// Outputs
// ============================================================
output apimGatewayUrl string = apim.properties.gatewayUrl
output apimResourceId string = apim.id
output apimIdentityPrincipalId string = apimIdentity.properties.principalId
output apimIdentityClientId string = apimIdentity.properties.clientId
output apimSubscriptionKeyHeader string = 'Ocp-Apim-Subscription-Key'
