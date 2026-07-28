// Azure Managed Redis (Enterprise) — for APIM external cache (semantic caching)
// SKU: Enterprise Balanced_B0 (smallest tier)
// Note: Classic Azure Cache for Redis is retired — using redisEnterprise
// TLS enforced, port 10000, hostname: {name}.{region}.redis.azure.net
param location string = resourceGroup().location
param redisCacheName string

resource redisEnterprise 'Microsoft.Cache/redisEnterprise@2024-10-01' = {
  name: redisCacheName
  location: location
  sku: {
    name: 'Balanced_B0'
  }
  properties: {
    minimumTlsVersion: '1.2'
  }
}

resource redisDatabase 'Microsoft.Cache/redisEnterprise/databases@2024-10-01' = {
  name: 'default'
  parent: redisEnterprise
  properties: {
    clientProtocol: 'Encrypted'
    clusteringPolicy: 'EnterpriseCluster'
    evictionPolicy: 'AllKeysLRU'
    port: 10000
  }
}

output redisHostName string = '${redisEnterprise.properties.hostName}'
output redisPort int = redisDatabase.properties.port
output redisCacheName string = redisEnterprise.name
#disable-next-line outputs-should-not-contain-secrets
output redisPrimaryKey string = redisDatabase.listKeys().primaryKey
#disable-next-line outputs-should-not-contain-secrets
output redisConnectionString string = '${redisEnterprise.properties.hostName}:${redisDatabase.properties.port},password=${redisDatabase.listKeys().primaryKey},ssl=True,abortConnect=False'
