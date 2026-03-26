// ====================================================================
// CONFIGURABLE PARAMETERS | PARÁMETROS CONFIGURABLES 
// ====================================================================
param location string = resourceGroup().location
// Sufijo único para evitar colisiones de nombres
param prefix string = 'nip'
param identityName string = 'nip-user-identity'
param sqlLocation string = 'centralus'
param projectName string = 'nip'
param containerImageTag string = 'latest'

// --- FASE 1: Identidad y Observabilidad ---

resource userIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
}

var logAnaliticsName = '${prefix}-log-analytics-${uniqueString(resourceGroup().id)}'
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logAnaliticsName
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

var appInsightsName = '${prefix}-app-insights-${uniqueString(resourceGroup().id)}'
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

var keyVaultName = '${prefix}kv${uniqueString(resourceGroup().id)}'
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true // Requerido para no usar Secrets tradicionales
    accessPolicies: []
  }
}

// --- FASE 2: Almacenamiento y Datos ---

var storageAccountName = toLower('${prefix}storage${uniqueString(resourceGroup().id)}')
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
  }
}

var containerRegistryName = '${prefix}ACR${uniqueString(resourceGroup().id)}'
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: containerRegistryName
  location: location
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false }
}

var sqlSeverName = '${prefix}-sql-server-${uniqueString(resourceGroup().id)}'
var sqlAdminName = identityName// Nombre de tu usuario de la UAMI
var sqlAdminObjectId = userIdentity.properties.principalId // referencia directa al principalId de la UAMI
resource sqlServer 'Microsoft.Sql/servers@2023-05-01-preview' = {
  name: sqlSeverName
  location: sqlLocation
  properties: {
    version: '12.0'
    administrators: {
      administratorType: 'ActiveDirectory'
      principalType: 'Application' // O 'Application' si usas la UAMI
      login: sqlAdminName
      sid: sqlAdminObjectId
      tenantId: subscription().tenantId
      azureADOnlyAuthentication: true
    }
  }
}

var sqlFirewallRuleName = 'AllowAllAzureIPs'
var sqlFirewallRuleStartIP = '0.0.0.0'
var sqlFirewallRuleEndIP = '255.255.255.255'
resource sqlFirewallRule 'Microsoft.Sql/servers/firewallRules@2023-05-01-preview' = {
  parent: sqlServer
  name: sqlFirewallRuleName
  properties: {
    startIpAddress: sqlFirewallRuleStartIP
    endIpAddress: sqlFirewallRuleEndIP
  }
}

var sqlServerDbName = '${prefix}-mssql-db'
var sqlServerDbLocation = sqlLocation
resource sqlDatabase 'Microsoft.Sql/servers/databases@2023-05-01-preview' = {
  parent: sqlServer
  name: sqlServerDbName
  location: sqlServerDbLocation
  sku: {
    name: 'GP_S_Gen5_1' // Serverless (Auto-pausa activada por defecto)
    tier: 'GeneralPurpose'
    family: 'Gen5'
    capacity: 1
  }  
}

// --- FASE 3: Azure AI Services ---

// Azure AI Foundry workspace
//var aiFoundryName = '${prefix}-foundry'
//var aiFoundryLocation = location
//var aiFoundryFriendlyName = 'NIP Foundry'
//resource aiFoundry 'Microsoft.MachineLearningServices/workspaces@2024-04-01-preview' = {
//  name: aiFoundryName
//  location: aiFoundryLocation
//  kind: 'Foundry'
//  identity: {
//    type: 'UserAssigned'
//    userAssignedIdentities: { '${userIdentity.id}': {} }
//  }
//  properties: {
//    friendlyName: aiFoundryFriendlyName
//    storageAccount: storageAccount.id
//    keyVault: keyVault.id
//    applicationInsights: appInsights.id
//  }
//}


var foundryServiceName = '${prefix}-project-${uniqueString(resourceGroup().id)}' 
var foundryServiceSku = 'S0'
resource foundryService 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: foundryServiceName
  location: location
  sku: { name: foundryServiceSku }
  kind: 'AIServices'
  properties: {
    customSubDomainName: '${projectName}-subdomain-foundry'
    publicNetworkAccess: 'Enabled'
  }
}

// Habilitar si se decide mantener los creados por Emilio
// resource foundryService 'Microsoft.CognitiveServices/accounts@2023-05-01' existing = {
//  name: foundryServiceName
//}

var speechServiceName = '${prefix}-speech-service-${uniqueString(resourceGroup().id)}'
var speechServiceSku = 'S0'
resource speechService 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: speechServiceName
  location: location
  sku: { name: speechServiceSku }
  kind: 'SpeechServices'
  properties: {
    customSubDomainName: '${projectName}-speech'
    publicNetworkAccess: 'Enabled'
  }
}

var contentSafetyName = '${prefix}-content-safety-${uniqueString(resourceGroup().id)}'
var contentSafetySku = 'S0'
resource contentSafety 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: contentSafetyName
  location: location
  sku: { name: contentSafetySku }
  kind: 'ContentSafety'
  properties: {
    customSubDomainName: '${projectName}-safety'
    publicNetworkAccess: 'Enabled'
  }
}

var gptDeploymentName = 'gpt-4o'
var gptDeploymentVersion = '2024-11-20'
resource gptDeployment 'Microsoft.CognitiveServices/accounts/deployments@2023-05-01' = {
  parent: foundryService
  name: gptDeploymentName
  sku: { 
    name: 'GlobalStandard'
    capacity: 100
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: gptDeploymentName
      version: gptDeploymentVersion
    }
  }
}

var gptMiniDeploymentName = 'gpt-4o-mini'
var gptMiniDeploymentVersion = '2024-07-18'
resource gptMiniDeployment 'Microsoft.CognitiveServices/accounts/deployments@2023-05-01' = {
  parent: foundryService
  name: gptMiniDeploymentName
  sku: { 
    name: 'GlobalStandard'
    capacity: 100
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: gptMiniDeploymentName
      version: gptMiniDeploymentVersion
    }
  }
  dependsOn: [
    gptDeployment
  ]
}

// --- FASE 4: Mensajería ---

var webPubSubName = '${prefix}-nexusinsight-${uniqueString(resourceGroup().id)}'
resource webPubSub 'Microsoft.SignalRService/webPubSub@2024-03-01' = {
  name: webPubSubName
  location: location
  sku: { name: 'Free_F1', capacity: 1 }
}

resource eventGridTopic 'Microsoft.EventGrid/systemTopics@2023-12-15-preview' = {
  name: '${prefix}-eventgrid-${uniqueString(resourceGroup().id)}'
  location: location
  properties: {
    source: storageAccount.id
    topicType: 'Microsoft.Storage.StorageAccounts'
  }
}

// --- FASE 5: Cómputo (Web Apps & Functions) ---

var appServiceWASku = 'B2' //'B1' // Mínimo para contenedores Linux
resource appServiceWAPlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: '${prefix}-wa-plan-${uniqueString(resourceGroup().id)}'
  location: location
  sku: { 
    name: appServiceWASku
    tier: 'Basic'
  }          
  kind: 'linux'
  properties: { reserved: true }
}

var webAppChatName = '${prefix}-app-chat-${uniqueString(resourceGroup().id)}'
var webAppChatImage = '${acr.properties.loginServer}/chat-app:${containerImageTag}'
resource webAppChat 'Microsoft.Web/sites@2023-01-01' = {
  name: webAppChatName
  location: location
  kind: 'app,linux,container'
  identity: {
    type: 'SystemAssigned, UserAssigned'
    userAssignedIdentities: { '${userIdentity.id}': {} }
  }
  properties: {
    serverFarmId: appServiceWAPlan.id
    siteConfig: {
      linuxFxVersion: 'DOCKER|${webAppChatImage}'
      appSettings: [
        {
          name: 'AZURE_STORAGE_ACCOUNT_KEY'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-STORAGE-ACCOUNT-KEY/)'
        }
        {
          name: 'AZURE_STORAGE_ACCOUNT_ENDPOINT'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-STORAGE-ACCOUNT-ENDPOINT/)'
        }
        {
          name: 'AZURE_SQL_CONNECTION_STRING'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-SQL-CONNECTION-STRING/)'
        }
        {
          name: 'AZURE_AI_PROJECT_ENDPOINT'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-AI-PROJECT-ENDPOINT/)'
        }
        {
          name: 'AZURE_AI_PROJECT_KEY'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-AI-PROJECT-KEY/)'
        }        
        {
          name: 'AZURE_SPEECH_ENDPOINT'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-SPEECH-ENDPOINT/)'
        }
        {
          name: 'AZURE_SPEECH_KEY'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-SPEECH-KEY/)'
        }
        {
          name: 'AZURE_CONTENT_SAFETY_ENDPOINT'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-CONTENT-SAFETY-ENDPOINT/)'
        }
        {
          name: 'AZURE_CONTENT_SAFETY_KEY'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-CONTENT-SAFETY-KEY/)'
        }
        {
          name: 'AZURE_DEPLOYMENT_GPT4OS_ENDPOINT'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-DEPLOYMENT-GPT4OS-ENDPOINT/)'
        }
        {
          name: 'AZURE_OPENAI_ENDPOINT' //Emilio lo nombró así, se puede unificar
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-DEPLOYMENT-GPT4OS-ENDPOINT/)'
        }        
        {
          name: 'AZURE_DEPLOYMENT_GPT4OS_KEY'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-DEPLOYMENT-GPT4OS-KEY/)'
        }
        {
          name: 'AZURE_OPENAI_API_KEY' //Emilio lo nombró así, se puede unificar
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-DEPLOYMENT-GPT4OS-KEY/)'
        }        
        {
          name: 'AZURE_DEPLOYMENT_GPT4OS_NAME'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-DEPLOYMENT-GPT4OS-NAME/)'
        }
        {
          name: 'AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME' //Emilio lo nombró así, se puede unificar
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-DEPLOYMENT-GPT4OS-NAME/)'
        }        
        {
          name: 'AZURE_DEPLOYMENT_GPT4OS_VERSION'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-DEPLOYMENT-GPT4OS-VERSION/)'
        }
        {
          name: 'AZURE_OPENAI_API_VERSION' //Emilio lo nombró así, se puede unificar
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-DEPLOYMENT-GPT4OS-VERSION/)'
        }        
        {
          name: 'AZURE_DEPLOYMENT_GPT4OM_ENDPOINT'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-DEPLOYMENT-GPT4OM-ENDPOINT/)'
        }
        {
          name: 'AZURE_DEPLOYMENT_GPT4OM_KEY'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-DEPLOYMENT-GPT4OM-KEY/)'
        }
        {
          name: 'AZURE_DEPLOYMENT_GPT4OM_NAME'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-DEPLOYMENT-GPT4OM-NAME/)'
        }
        {
          name: 'AZURE_DEPLOYMENT_GPT4OM_VERSION'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-DEPLOYMENT-GPT4OM-VERSION/)'
        }
        {
          name: 'AZURE_WEBPUBSUB_ENDPOINT'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-WEBPUBSUB-ENDPOINT/)'
        }
        {
          name: 'AZURE_WEBPUBSUB_HOSTNAME'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-WEBPUBSUB-HOSTNAME/)'
        }
        {
          name: 'AZURE_WEBPUBSUB_KEY'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-WEBPUBSUB-KEY/)'
        }
        {
          name: 'AZURE_WEBPUBSUB_CONNECTION_STRING'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-WEBPUBSUB-CONNECTION-STRING/)'
        }
        {
          name: 'AZURE_WEBPUBSUB_HUB_NAME'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-WEBPUBSUB-HUB-NAME/)'
        }
        {
          name: 'AZURE_WEBPUBSUB_GROUP'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-WEBPUBSUB-GROUP/)'
        }
        {
          name: 'AZURE_CLIENT_ID'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-CLIENT-ID/)'
        }
        {
          name: 'AZURE_CLIENT_SECRET'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-CLIENT-SECRET/)'
        }
        {
          name: 'AZURE_TENANT_ID'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-TENANT-ID/)'
        }
      ]
    }
  }
}

var webAppNeiName = '${prefix}-app-nei-${uniqueString(resourceGroup().id)}'
var webAppNeiImage = '${acr.properties.loginServer}/nei-app:${containerImageTag}'
resource webAppNei 'Microsoft.Web/sites@2023-01-01' = {
  name: webAppNeiName
  location: location
  kind: 'app,linux,container'
  identity: {
    type: 'SystemAssigned, UserAssigned'
    userAssignedIdentities: { '${userIdentity.id}': {} }
  }
  properties: {
    serverFarmId: appServiceWAPlan.id
    siteConfig: {
      linuxFxVersion: 'DOCKER|${webAppNeiImage}'
      appSettings: [
        {
          name: 'AZURE_STORAGE_ACCOUNT_KEY'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-STORAGE-ACCOUNT-KEY/)'
        }
        {
          name: 'AZURE_STORAGE_ACCOUNT_ENDPOINT'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-STORAGE-ACCOUNT-ENDPOINT/)'
        }
        {
          name: 'AZURE_SQL_CONNECTION_STRING'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-SQL-CONNECTION-STRING/)'
        }
        {
          name: 'AZURE_AI_PROJECT_ENDPOINT'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-AI-PROJECT-ENDPOINT/)'
        }
        {
          name: 'AZURE_AI_PROJECT_KEY'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-AI-PROJECT-KEY/)'
        }        
        {
          name: 'AZURE_SPEECH_ENDPOINT'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-SPEECH-ENDPOINT/)'
        }
        {
          name: 'AZURE_SPEECH_KEY'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-SPEECH-KEY/)'
        }
        {
          name: 'AZURE_CONTENT_SAFETY_ENDPOINT'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-CONTENT-SAFETY-ENDPOINT/)'
        }
        {
          name: 'AZURE_CONTENT_SAFETY_KEY'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-CONTENT-SAFETY-KEY/)'
        }
        {
          name: 'AZURE_DEPLOYMENT_GPT4OS_ENDPOINT'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-DEPLOYMENT-GPT4OS-ENDPOINT/)'
        }
        {
          name: 'AZURE_OPENAI_ENDPOINT' //Emilio lo nombró así, se puede unificar
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-DEPLOYMENT-GPT4OS-ENDPOINT/)'
        }        
        {
          name: 'AZURE_DEPLOYMENT_GPT4OS_KEY'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-DEPLOYMENT-GPT4OS-KEY/)'
        }
        {
          name: 'AZURE_OPENAI_API_KEY' //Emilio lo nombró así, se puede unificar
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-DEPLOYMENT-GPT4OS-KEY/)'
        }        
        {
          name: 'AZURE_DEPLOYMENT_GPT4OS_NAME'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-DEPLOYMENT-GPT4OS-NAME/)'
        }
        {
          name: 'AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME' //Emilio lo nombró así, se puede unificar
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-DEPLOYMENT-GPT4OS-NAME/)'
        }        
        {
          name: 'AZURE_DEPLOYMENT_GPT4OS_VERSION'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-DEPLOYMENT-GPT4OS-VERSION/)'
        }
        {
          name: 'AZURE_OPENAI_API_VERSION' //Emilio lo nombró así, se puede unificar
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-DEPLOYMENT-GPT4OS-VERSION/)'
        }        
        {
          name: 'AZURE_DEPLOYMENT_GPT4OM_ENDPOINT'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-DEPLOYMENT-GPT4OM-ENDPOINT/)'
        }
        {
          name: 'AZURE_DEPLOYMENT_GPT4OM_KEY'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-DEPLOYMENT-GPT4OM-KEY/)'
        }
        {
          name: 'AZURE_DEPLOYMENT_GPT4OM_NAME'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-DEPLOYMENT-GPT4OM-NAME/)'
        }
        {
          name: 'AZURE_DEPLOYMENT_GPT4OM_VERSION'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-DEPLOYMENT-GPT4OM-VERSION/)'
        }
        {
          name: 'AZURE_WEBPUBSUB_ENDPOINT'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-WEBPUBSUB-ENDPOINT/)'
        }
        {
          name: 'AZURE_WEBPUBSUB_HOSTNAME'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-WEBPUBSUB-HOSTNAME/)'
        }
        {
          name: 'AZURE_WEBPUBSUB_KEY'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-WEBPUBSUB-KEY/)'
        }
        {
          name: 'AZURE_WEBPUBSUB_CONNECTION_STRING'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-WEBPUBSUB-CONNECTION-STRING/)'
        }
        {
          name: 'AZURE_WEBPUBSUB_HUB_NAME'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-WEBPUBSUB-HUB-NAME/)'
        }
        {
          name: 'AZURE_WEBPUBSUB_GROUP'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-WEBPUBSUB-GROUP/)'
        }
        {
          name: 'AZURE_CLIENT_ID'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-CLIENT-ID/)'
        }
        {
          name: 'AZURE_CLIENT_SECRET'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-CLIENT-SECRET/)'
        }
        {
          name: 'AZURE_TENANT_ID'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVault.name}.vault.azure.net/secrets/AZURE-TENANT-ID/)'
        }
      ]
    }
  }
}

var appServiceFASku = 'Y1' //'B1' // Mínimo para contenedores Linux
resource appServiceFAPlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: '${prefix}-fa-plan-${uniqueString(resourceGroup().id)}'
  location: location
  sku: { 
    name: appServiceFASku
    tier: 'Dynamic' // 'Basic' para B1, 'Dynamic' para Y1 (consumption)
  }          
  kind: 'linux'
  properties: { reserved: true }
}

resource functionApp 'Microsoft.Web/sites@2023-01-01' = {
  name: '${prefix}-durable-functions-${uniqueString(resourceGroup().id)}'
  location: location
  kind: 'functionapp,linux'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${userIdentity.id}': {} }
  }
  properties: {
    serverFarmId: appServiceFAPlan.id
    httpsOnly: true
    siteConfig: {
      appSettings: [
        { name: 'AzureWebJobsStorage__accountName', value: storageAccount.name }
        { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4' }
        { name: 'FUNCTIONS_WORKER_RUNTIME', value: 'python' }
      ]
    }
  }
}

// --- FASE 6: Gateway ---

resource apiManagement 'Microsoft.ApiManagement/service@2023-05-01-preview' = {
  name: '${prefix}-apim-${uniqueString(resourceGroup().id)}'
  location: location
  sku: { name: 'Consumption', capacity: 0 }
  properties: {
    publisherEmail: 'luis.sanchez@gmail.com'
    publisherName: 'Nexus Insight Planning'
  }
}

// --- ASIGNACIÓN DE ROLES (RBAC) ---
// Role IDs:
// Cognitive Services User: a97b65f3-24c7-4388-baec-2e87135dc908
// Storage Blob Data Contributor: ba92f572-3b2b-4ada-a4c3-bc0d74139962
// AcrPull: 7f951dda-a305-4103-bb46-7748c0d519ad

resource roleContentSafety 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(contentSafety.id, userIdentity.id, 'Cognitive Services User')
  scope: contentSafety
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
    principalId: userIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource roleStorage 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, userIdentity.id, 'Storage Blob Data Contributor')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: userIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
  dependsOn: [
    roleContentSafety
  ]
}

resource roleAcr 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, userIdentity.id, 'AcrPull')
  scope: acr
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: userIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
  dependsOn: [
    roleStorage
  ]
}

resource roleSqlAdmins 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(sqlDatabase.id, userIdentity.id, 'SQL DB Contributor')
  scope: sqlDatabase
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '9b7fa17d-e63e-47b0-bb0a-15c516ac86ec') // SQL DB Contributor
    principalId: userIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
  dependsOn: [
    roleAcr
  ]
}

resource roleSqlReaders 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(sqlDatabase.id, userIdentity.id, 'SQL DB Reader')
  scope: sqlDatabase
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'c6bd0a5c-0ce2-465d-8e45-abe7c6e0d2f9') // SQL DB Reader
    principalId: userIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
  dependsOn: [
    roleSqlAdmins
  ]
}

//resource roleKeyVaultReaders 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
//  name: guid(keyVault.id, userIdentity.id, 'KEY VAULT Reader')
//  scope: keyVault
//  properties: {
//    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'acdd72a7-3385-48ef-bd42-f606fba81ae7') // Key Vault Reader
//    principalId: userIdentity.properties.principalId
//    principalType: 'ServicePrincipal'
//  }
//}

resource roleKeyVaultSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, userIdentity.id, 'Key Vault Secrets User')
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions','4633458b-17de-408a-b874-0445c86b69e6' // Key Vault Secrets User
    )
    principalId: userIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ===========================================================================
// How to deploy
// 1. Log in to Azure
// 2. Get the object ID (for the `mainId` parameter)
// 3. Deploy the infrastructure (run)
// Note: A new tenant requires that the service (namespace) be registered beforehand
// (e.g., `az provider register --namespace Microsoft.KeyVault`)
//
// Cómo desplegar
// 1. Login a Azure
// 2. Obtener ID de Objeto (para el parámetro principalId)
// 3. Desplegar la infraestructura (ejecución)
// Nota: Un Tenat nuevo requiere registrar el servicio (namespace) previamente
// (pe: az provider register --namespace Microsoft.KeyVault)
// ===========================================================================
// $ az login --tenant <TENANT-ID> or az login --use-device-code --tenant <TENANT_ID>
// $ az ad signed-in-user show --query id --output tsv
// $ az account set --subscription '<SUSCRIPTION_ID>'
// $ az group create \
//      --name <resource-group-name> \
//      --location <location>
// $ az deployment group create \
//      --resource-group <resource-group-name> \
//      --template-file <main.bicep> \
//      --parameters postgresAdminPassword='<PASSWORD_POSTGRESQL>'
//
