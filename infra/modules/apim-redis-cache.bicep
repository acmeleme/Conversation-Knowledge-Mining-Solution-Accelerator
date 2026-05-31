// APIM External Cache — connects Azure Managed Redis as APIM's external cache
// Resource: Microsoft.ApiManagement/service/caches
// Cache region 'default' = global cache shared across all APIM regions
// Azure Managed Redis connection: {host}:10000,password={key},ssl=True,abortConnect=False
// Note: port is 10000 for Azure Managed Redis (NOT 6380 which was Azure Cache for Redis)
param apimName string
param redisHostName string
param redisPort int = 10000
@secure()
param redisKey string

var redisConnectionString = '${redisHostName}:${redisPort},password=${redisKey},ssl=True,abortConnect=False'

resource apimService 'Microsoft.ApiManagement/service@2023-05-01-preview' existing = {
  name: apimName
}

resource apimExternalCache 'Microsoft.ApiManagement/service/caches@2023-05-01-preview' = {
  name: 'default'
  parent: apimService
  properties: {
    connectionString: redisConnectionString
    useFromLocation: 'default'
    description: 'Azure Managed Redis — semantic cache for chart and AI responses'
  }
}

output cacheId string = apimExternalCache.id
output cacheLocation string = apimExternalCache.properties.useFromLocation
