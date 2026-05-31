param name string
param location string = resourceGroup().location
param apimPrincipalId string
param tags object = {}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: name
  location: location
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: false
    accessPolicies: [
      {
        tenantId: subscription().tenantId
        objectId: apimPrincipalId
        permissions: {
          secrets: [
            'get'
            'list'
          ]
        }
      }
    ]
  }
  tags: tags
}

output vaultUri string = keyVault.properties.vaultUri
output resourceId string = keyVault.id
