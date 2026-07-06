targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the azd environment (used to derive resource names).')
param environmentName string

@minLength(1)
@description('Azure region for all resources.')
param location string

// Optional principalId (set by azd for the current user); left blank in CI.
param principalId string = ''

// Deterministic-but-unique token that keeps global names (ACR) unique per env.
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = { 'azd-env-name': environmentName }

resource rg 'Microsoft.Resources/resourceGroups@2022-09-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

module resources 'resources.bicep' = {
  name: 'resources'
  scope: rg
  params: {
    location: location
    resourceToken: resourceToken
    tags: tags
    principalId: principalId
  }
}

output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = resources.outputs.containerRegistryEndpoint
output AZURE_CONTAINER_REGISTRY_NAME string = resources.outputs.containerRegistryName
output AZURE_CONTAINER_APPS_ENVIRONMENT_ID string = resources.outputs.containerAppsEnvironmentId
output SERVICE_MCP_SERVER_ENDPOINT_URL string = resources.outputs.mcpServerUrl
