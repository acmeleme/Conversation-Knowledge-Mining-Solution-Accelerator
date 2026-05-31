// Azure Managed Redis — for APIM external cache (semantic caching)
// SKU: Balanced_B0 (1 GB) — cost-effective for demo/dev workloads
// Note: Azure Cache for Redis (Basic/Standard/Premium) is retiring — use Azure Managed Redis
// Resource: Microsoft.Cache/redisEnterprise (cluster) + database/default
// TLS enforced, port 10000, hostname: {name}.{region}.redis.azure.net
param location string = resourceGroup().location
param redisCacheName string

resource redisCluster 'Microsoft.Cache/redisEnterprise@2024-10-01' = {
  name: redisCacheName
  location: location
  sku: {
    name: 'Balanced_B0'
    capacity: 1
  }
  properties: {
    publicNetworkAccess: 'Enabled'
  }
}

resource redisDatabase 'Microsoft.Cache/redisEnterprise/databases@2024-10-01' = {
  name: 'default'
  parent: redisCluster
  properties: {
    evictionPolicy: 'AllKeysLRU'
    clusteringPolicy: 'OSSCluster'
    port: 10000
  }
}

output redisHostName string = redisCluster.properties.hostName
output redisPort int = 10000
#disable-next-line outputs-should-not-contain-secrets
output redisPrimaryKey string = redisDatabase.listKeys().primaryKey
