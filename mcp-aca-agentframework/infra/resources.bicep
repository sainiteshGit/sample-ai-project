param location string
param resourceToken string
param tags object
param principalId string

// -------- Log Analytics (required by Container Apps Environment) --------
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: 'log-${resourceToken}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

// -------- User-assigned managed identity (used by ACA to pull from ACR) --------
resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${resourceToken}'
  location: location
  tags: tags
}

// -------- Azure Container Registry --------
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: 'acr${resourceToken}'
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
  }
}

// AcrPull role for the managed identity so ACA can pull the image.
resource acrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, identity.id, 'AcrPull')
  scope: acr
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    // AcrPull role definition ID (well-known).
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '7f951dda-4ed3-4680-a7ca-43fe172d538d'
    )
  }
}

// AcrPush for the deploying user so `azd deploy` can push the built image.
resource acrPushRoleForUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  name: guid(acr.id, principalId, 'AcrPush')
  scope: acr
  properties: {
    principalId: principalId
    principalType: 'User'
    // AcrPush
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '8311e382-0749-4cb8-b61a-304f252e45ec'
    )
  }
}

// -------- Container Apps Environment --------
resource acaEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-${resourceToken}'
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

// -------- The MCP server Container App --------
// Uses a public "hello-world" image at first-provision time; `azd deploy` will
// build our real image and update this app to point at it.
resource mcpServerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-mcp-server-${resourceToken}'
  location: location
  // Tag makes azd map service 'mcp-server' (from azure.yaml) to THIS app.
  tags: union(tags, { 'azd-service-name': 'mcp-server' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: acaEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8080
        transport: 'auto'      // HTTP/1.1 + HTTP/2 auto-negotiate (works for MCP streamable HTTP).
        allowInsecure: false
      }
      registries: [
        {
          server: acr.properties.loginServer
          identity: identity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'mcp-server'
          image: 'mcr.microsoft.com/k8se/quickstart:latest'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'PORT', value: '8080' }
            { name: 'ASPNETCORE_URLS', value: 'http://+:8080' }
          ]
        }
      ]
      scale: {
        minReplicas: 0     // scale-to-zero: pay nothing when idle
        maxReplicas: 3
      }
    }
  }
}

output containerRegistryEndpoint string = acr.properties.loginServer
output containerRegistryName string = acr.name
output containerAppsEnvironmentId string = acaEnv.id
output mcpServerUrl string = 'https://${mcpServerApp.properties.configuration.ingress.fqdn}/mcp'
