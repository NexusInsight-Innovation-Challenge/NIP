@description('Deployment location')
param location string = resourceGroup().location

@description('Environment name used by azd for resource naming')
param environmentName string

@description('Azure Web PubSub connection string secret')
@secure()
param AZURE_WEBPUBSUB_CONNECTION_STRING string

@description('Azure Web PubSub hub name')
param AZURE_WEBPUBSUB_HUB_NAME string

@description('Azure Web PubSub group name')
param AZURE_WEBPUBSUB_GROUP string

@description('Container app minimum replicas')
param containerAppMinReplicas int = 1

@description('Container app maximum replicas')
param containerAppMaxReplicas int = 2

var tags = {
  'azd-env-name': environmentName
  'azd-service-name': 'web'
}

var workspaceName = 'law-${uniqueString(resourceGroup().id, environmentName)}'
var managedEnvironmentName = 'cae-${environmentName}'
var containerRegistryName = replace('acr${uniqueString(resourceGroup().id, environmentName)}', '-', '')
var containerAppName = 'ca-${environmentName}-web'

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: workspaceName
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: containerRegistryName
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
  }
}

resource containerAppEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: managedEnvironmentName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  tags: tags
  properties: {
    environmentId: containerAppEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 3000
        transport: 'auto'
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: 'system'
        }
      ]
      secrets: [
        {
          name: 'webpubsub-connection-string'
          value: AZURE_WEBPUBSUB_CONNECTION_STRING
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'web'
          image: '${containerRegistry.properties.loginServer}/innovation-challenge-chat-web:latest'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            {
              name: 'NODE_ENV'
              value: 'production'
            }
            {
              name: 'PORT'
              value: '3000'
            }
            {
              name: 'HOSTNAME'
              value: '0.0.0.0'
            }
            {
              name: 'AZURE_WEBPUBSUB_HUB_NAME'
              value: AZURE_WEBPUBSUB_HUB_NAME
            }
            {
              name: 'AZURE_WEBPUBSUB_GROUP'
              value: AZURE_WEBPUBSUB_GROUP
            }
            {
              name: 'AZURE_WEBPUBSUB_CONNECTION_STRING'
              secretRef: 'webpubsub-connection-string'
            }
          ]
        }
      ]
      scale: {
        minReplicas: containerAppMinReplicas
        maxReplicas: containerAppMaxReplicas
      }
    }
  }
}

resource acrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerRegistry.id, containerApp.id, 'acrpull')
  scope: containerRegistry
  properties: {
    principalId: containerApp.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalType: 'ServicePrincipal'
  }
}

output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.properties.loginServer
output AZURE_CONTAINER_APP_NAME string = containerApp.name
output AZURE_CONTAINER_APP_URL string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
output AZURE_RESOURCE_GROUP_NAME string = resourceGroup().name
