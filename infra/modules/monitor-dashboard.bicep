// ============================================================
// Azure Monitor Dashboard — APIM Token Usage & Performance
// Phase 2: Observability for CKM AI Gateway
// ============================================================

@description('Resource name prefix (e.g., callcenter100)')
param resourceName string

@description('Azure region for dashboard deployment')
param location string = resourceGroup().location

@description('APIM service name')
param apimServiceName string

@description('Application Insights name')
param appInsightsName string

// ============================================================
// Build resource IDs from context
// ============================================================
var subscriptionId = subscription().subscriptionId
var rgName = resourceGroup().name
var apimResourceId = '/subscriptions/${subscriptionId}/resourceGroups/${rgName}/providers/Microsoft.ApiManagement/service/${apimServiceName}'
var appInsightsComponentId = {
  SubscriptionId: subscriptionId
  ResourceGroup: rgName
  Name: appInsightsName
  ResourceType: 'microsoft.insights/components'
}

// ============================================================
// Azure Monitor Dashboard
// ============================================================
resource dashboard 'Microsoft.Portal/dashboards@2022-12-01-preview' = {
  name: 'dash-${resourceName}-apim'
  location: location
  tags: {
    'hidden-title': 'CKM AI Gateway — APIM Dashboard'
    project: 'conversation-knowledge-mining'
    phase: '2'
  }
  properties: {
    lenses: [
      {
        order: 0
        parts: [
          // ── Tile 0: Dashboard Title ────────────────────────────────
          {
            position: {
              x: 0
              y: 0
              colSpan: 12
              rowSpan: 1
            }
            metadata: {
              type: 'Extension/HubsExtension/PartType/MarkdownPart'
              inputs: []
              settings: {
                content: {
                  settings: {
                    content: '## 🤖 CKM AI Gateway — APIM Dashboard\nReal-time token usage, request rates, and performance metrics for the Conversation Knowledge Mining AI Gateway.'
                    title: ''
                    subtitle: ''
                    markdownSource: 1
                  }
                }
              }
            }
          }
          // ── Tile 1: APIM Total Requests ────────────────────────────
          {
            position: {
              x: 0
              y: 1
              colSpan: 4
              rowSpan: 3
            }
            metadata: {
              type: 'Extension/Microsoft_Azure_MonitoringMetrics/PartType/MetricsChartPart'
              inputs: [
                {
                  name: 'options'
                  isOptional: true
                }
                {
                  name: 'sharedTimeRange'
                  isOptional: true
                }
              ]
              settings: {
                content: {
                  options: {
                    chart: {
                      metrics: [
                        {
                          resourceMetadata: {
                            id: apimResourceId
                          }
                          name: 'TotalRequests'
                          aggregationType: 1
                          namespace: 'microsoft.apimanagement/service'
                          metricVisualization: {
                            displayName: 'Total Requests'
                            color: '#0078D4'
                          }
                        }
                      ]
                      title: 'APIM — Total Requests'
                      titleKind: 1
                      visualization: {
                        chartType: 2
                        legendVisualization: {
                          isVisible: true
                          position: 2
                          hideSubtitle: false
                        }
                        axisVisualization: {
                          x: {
                            isVisible: true
                            axisType: 2
                          }
                          y: {
                            isVisible: true
                            axisType: 1
                          }
                        }
                      }
                      timespan: {
                        relative: {
                          duration: 86400000
                        }
                        showUTCTime: false
                        grain: 1
                      }
                    }
                  }
                }
              }
            }
          }
          // ── Tile 2: APIM Failed Requests ───────────────────────────
          {
            position: {
              x: 4
              y: 1
              colSpan: 4
              rowSpan: 3
            }
            metadata: {
              type: 'Extension/Microsoft_Azure_MonitoringMetrics/PartType/MetricsChartPart'
              inputs: [
                {
                  name: 'options'
                  isOptional: true
                }
                {
                  name: 'sharedTimeRange'
                  isOptional: true
                }
              ]
              settings: {
                content: {
                  options: {
                    chart: {
                      metrics: [
                        {
                          resourceMetadata: {
                            id: apimResourceId
                          }
                          name: 'FailedRequests'
                          aggregationType: 1
                          namespace: 'microsoft.apimanagement/service'
                          metricVisualization: {
                            displayName: 'Failed Requests'
                            color: '#E81123'
                          }
                        }
                      ]
                      title: 'APIM — Failed Requests'
                      titleKind: 1
                      visualization: {
                        chartType: 2
                        legendVisualization: {
                          isVisible: true
                          position: 2
                          hideSubtitle: false
                        }
                        axisVisualization: {
                          x: {
                            isVisible: true
                            axisType: 2
                          }
                          y: {
                            isVisible: true
                            axisType: 1
                          }
                        }
                      }
                      timespan: {
                        relative: {
                          duration: 86400000
                        }
                        showUTCTime: false
                        grain: 1
                      }
                    }
                  }
                }
              }
            }
          }
          // ── Tile 3: APIM Gateway Capacity ──────────────────────────
          {
            position: {
              x: 8
              y: 1
              colSpan: 4
              rowSpan: 3
            }
            metadata: {
              type: 'Extension/Microsoft_Azure_MonitoringMetrics/PartType/MetricsChartPart'
              inputs: [
                {
                  name: 'options'
                  isOptional: true
                }
                {
                  name: 'sharedTimeRange'
                  isOptional: true
                }
              ]
              settings: {
                content: {
                  options: {
                    chart: {
                      metrics: [
                        {
                          resourceMetadata: {
                            id: apimResourceId
                          }
                          name: 'Capacity'
                          aggregationType: 4
                          namespace: 'microsoft.apimanagement/service'
                          metricVisualization: {
                            displayName: 'Capacity (%)'
                            color: '#FFB900'
                          }
                        }
                      ]
                      title: 'APIM — Gateway Capacity'
                      titleKind: 1
                      visualization: {
                        chartType: 2
                        legendVisualization: {
                          isVisible: true
                          position: 2
                          hideSubtitle: false
                        }
                        axisVisualization: {
                          x: {
                            isVisible: true
                            axisType: 2
                          }
                          y: {
                            isVisible: true
                            axisType: 1
                          }
                        }
                      }
                      timespan: {
                        relative: {
                          duration: 86400000
                        }
                        showUTCTime: false
                        grain: 1
                      }
                    }
                  }
                }
              }
            }
          }
          // ── Tile 5: APIM Success vs Failed ─────────────────────────
          {
            position: {
              x: 6
              y: 4
              colSpan: 6
              rowSpan: 4
            }
            metadata: {
              type: 'Extension/Microsoft_Azure_MonitoringMetrics/PartType/MetricsChartPart'
              inputs: [
                {
                  name: 'options'
                  isOptional: true
                }
                {
                  name: 'sharedTimeRange'
                  isOptional: true
                }
              ]
              settings: {
                content: {
                  options: {
                    chart: {
                      metrics: [
                        {
                          resourceMetadata: {
                            id: apimResourceId
                          }
                          name: 'SuccessfulRequests'
                          aggregationType: 1
                          namespace: 'microsoft.apimanagement/service'
                          metricVisualization: {
                            displayName: 'Successful Requests'
                            color: '#107C10'
                          }
                        }
                        {
                          resourceMetadata: {
                            id: apimResourceId
                          }
                          name: 'FailedRequests'
                          aggregationType: 1
                          namespace: 'microsoft.apimanagement/service'
                          metricVisualization: {
                            displayName: 'Failed Requests'
                            color: '#E81123'
                          }
                        }
                      ]
                      title: 'APIM — Success vs Failed'
                      titleKind: 1
                      visualization: {
                        chartType: 2
                        legendVisualization: {
                          isVisible: true
                          position: 2
                          hideSubtitle: false
                        }
                        axisVisualization: {
                          x: {
                            isVisible: true
                            axisType: 2
                          }
                          y: {
                            isVisible: true
                            axisType: 1
                          }
                        }
                      }
                      timespan: {
                        relative: {
                          duration: 86400000
                        }
                        showUTCTime: false
                        grain: 1
                      }
                    }
                  }
                }
              }
            }
          }
          // ── Tile 7: APIM Response Duration ─────────────────────────
          {
            position: {
              x: 6
              y: 8
              colSpan: 6
              rowSpan: 4
            }
            metadata: {
              type: 'Extension/Microsoft_Azure_MonitoringMetrics/PartType/MetricsChartPart'
              inputs: [
                {
                  name: 'options'
                  isOptional: true
                }
                {
                  name: 'sharedTimeRange'
                  isOptional: true
                }
              ]
              settings: {
                content: {
                  options: {
                    chart: {
                      metrics: [
                        {
                          resourceMetadata: {
                            id: apimResourceId
                          }
                          name: 'TotalDuration'
                          aggregationType: 4
                          namespace: 'microsoft.apimanagement/service'
                          metricVisualization: {
                            displayName: 'Avg Response Duration (ms)'
                            color: '#8764B8'
                          }
                        }
                      ]
                      title: 'APIM — Average Response Duration'
                      titleKind: 1
                      visualization: {
                        chartType: 2
                        legendVisualization: {
                          isVisible: true
                          position: 2
                          hideSubtitle: false
                        }
                        axisVisualization: {
                          x: {
                            isVisible: true
                            axisType: 2
                          }
                          y: {
                            isVisible: true
                            axisType: 1
                          }
                        }
                      }
                      timespan: {
                        relative: {
                          duration: 86400000
                        }
                        showUTCTime: false
                        grain: 1
                      }
                    }
                  }
                }
              }
            }
          }
        ]
      }
    ]
    metadata: {
      model: {
        timeRange: {
          value: {
            relative: {
              duration: 24
              timeUnit: 1
            }
          }
          type: 'MsPortalFx.Composition.Configuration.ValueTypes.TimeRange'
        }
        filterLocale: {
          value: 'en-us'
        }
        filters: {
          value: {
            MsPortalFx_TimeRange: {
              model: {
                format: 'utc'
                granularity: 'auto'
                relative: '24h'
              }
              displayCache: {
                name: 'UTC Time'
                value: 'Past 24 hours'
              }
              filteredPartIds: []
            }
          }
        }
      }
    }
  }
}

// ============================================================
// Outputs
// ============================================================
output dashboardId string = dashboard.id
output dashboardName string = dashboard.name
