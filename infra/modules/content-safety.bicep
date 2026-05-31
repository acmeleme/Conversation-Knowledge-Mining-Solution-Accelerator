param name string
param location string = resourceGroup().location
param sku string = 'S0'
param tags object = {}

resource contentSafety 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: name
  location: location
  kind: 'ContentSafety'
  sku: {
    name: sku
  }
  properties: {
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
    }
  }
  tags: tags
}

output endpoint string = contentSafety.properties.endpoint
output resourceId string = contentSafety.id
output name string = contentSafety.name
