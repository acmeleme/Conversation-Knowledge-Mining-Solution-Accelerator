param(
    [Parameter(Mandatory = $true)]
    [string]$ResourceGroup,

    [string]$ImageTag
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($ImageTag)) {
    $ImageTag = "app-only-$(Get-Date -Format yyyyMMddHHmmss)"
}

Write-Host "Deploying application only to resource group: $ResourceGroup"

if ([string]::IsNullOrWhiteSpace($env:APP_NAME)) {
    $appName = az webapp list --resource-group $ResourceGroup --query "[?starts_with(name, 'app-')].name | [0]" -o tsv
} else {
    $appName = $env:APP_NAME
}
if ([string]::IsNullOrWhiteSpace($env:API_NAME)) {
    $apiName = az webapp list --resource-group $ResourceGroup --query "[?starts_with(name, 'api-')].name | [0]" -o tsv
} else {
    $apiName = $env:API_NAME
}

if ([string]::IsNullOrWhiteSpace($appName) -or [string]::IsNullOrWhiteSpace($apiName)) {
    throw "Could not discover app/api App Services in resource group '$ResourceGroup'."
}

$appFx = $null
$apiFx = $null
if ([string]::IsNullOrWhiteSpace($env:APP_REPO) -or [string]::IsNullOrWhiteSpace($env:API_REPO) -or [string]::IsNullOrWhiteSpace($env:ACR_LOGIN_SERVER)) {
    $appFx = az webapp config container show --resource-group $ResourceGroup --name $appName --query "[?name=='DOCKER_CUSTOM_IMAGE_NAME'].value | [0]" -o tsv
    $apiFx = az webapp config container show --resource-group $ResourceGroup --name $apiName --query "[?name=='DOCKER_CUSTOM_IMAGE_NAME'].value | [0]" -o tsv
}

$appImageRef = ($appFx -replace '^DOCKER\|', '')
$apiImageRef = ($apiFx -replace '^DOCKER\|', '')

$appRepo = $env:APP_REPO
$apiRepo = $env:API_REPO

if ($appImageRef -match '/') {
    $appRepoWithTag = $appImageRef.Split('/', 2)[1]
    $appRepo = $appRepoWithTag.Split(':', 2)[0]
}

if ($apiImageRef -match '/') {
    $apiRepoWithTag = $apiImageRef.Split('/', 2)[1]
    $apiRepo = $apiRepoWithTag.Split(':', 2)[0]
}

if ([string]::IsNullOrWhiteSpace($env:ACR_LOGIN_SERVER)) {
    $acrLoginServer = az acr list --resource-group $ResourceGroup --query "[0].loginServer" -o tsv
} else {
    $acrLoginServer = $env:ACR_LOGIN_SERVER
}
if ([string]::IsNullOrWhiteSpace($acrLoginServer)) {
    $acrLoginServer = $env:AZURE_CONTAINER_REGISTRY_ENDPOINT
}
if ([string]::IsNullOrWhiteSpace($acrLoginServer)) {
    $acrEnv = azd env get-value AZURE_CONTAINER_REGISTRY_ENDPOINT 2>$null
    if (-not [string]::IsNullOrWhiteSpace($acrEnv)) {
        $acrLoginServer = $acrEnv
    }
}
if ([string]::IsNullOrWhiteSpace($acrLoginServer)) {
    $acrNameEnv = azd env get-value ACR_NAME 2>$null
    if (-not [string]::IsNullOrWhiteSpace($acrNameEnv)) {
        $acrLoginServer = "$acrNameEnv.azurecr.io"
    }
}
if ([string]::IsNullOrWhiteSpace($acrLoginServer)) {
    $acrLoginServer = az acr list --query "[0].loginServer" -o tsv
}
if ([string]::IsNullOrWhiteSpace($acrLoginServer) -and $appImageRef -match '/') {
    $acrLoginServer = $appImageRef.Split('/', 2)[0]
}
if ([string]::IsNullOrWhiteSpace($acrLoginServer)) {
    throw "Could not resolve ACR endpoint. Set AZURE_CONTAINER_REGISTRY_ENDPOINT or azd env ACR values."
}

$acrName = $acrLoginServer.Split('.', 2)[0]

if ([string]::IsNullOrWhiteSpace($appRepo)) { $appRepo = $appName }
if ([string]::IsNullOrWhiteSpace($apiRepo)) { $apiRepo = $apiName }

$appImage = "$acrLoginServer/${appRepo}:$ImageTag"
$apiImage = "$acrLoginServer/${apiRepo}:$ImageTag"

Write-Host "Using ACR: $acrLoginServer"
Write-Host "Web app: $appName"
Write-Host "API app: $apiName"
Write-Host "Image tag: $ImageTag"

az acr login --name $acrName | Out-Null

$dockerAvailable = $false
try {
    docker version | Out-Null
    if ($LASTEXITCODE -eq 0) {
        $dockerAvailable = $true
    }
} catch {
    $dockerAvailable = $false
}

if (-not $dockerAvailable) {
    throw "Local Docker daemon is required for image generation. Remote ACR build is not allowed."
}

Write-Host "Building and pushing frontend image..."
docker build --platform linux/amd64 -f src/App/WebApp.Dockerfile -t $appImage src/App
if ($LASTEXITCODE -ne 0) { throw "Frontend image build failed." }
docker push $appImage
if ($LASTEXITCODE -ne 0) { throw "Frontend image push failed." }

Write-Host "Building and pushing API image..."
docker build --platform linux/amd64 -f src/api/ApiApp.Dockerfile -t $apiImage src/api
if ($LASTEXITCODE -ne 0) { throw "API image build failed." }
docker push $apiImage
if ($LASTEXITCODE -ne 0) { throw "API image push failed." }

Write-Host "Updating App Service container configuration..."
az webapp config container set --resource-group $ResourceGroup --name $appName --container-image-name $appImage --container-registry-url "https://$acrLoginServer" | Out-Null
az webapp config container set --resource-group $ResourceGroup --name $apiName --container-image-name $apiImage --container-registry-url "https://$acrLoginServer" | Out-Null

$authSettingsUrl = "https://management.azure.com/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$ResourceGroup/providers/Microsoft.Web/sites/$appName/config/authsettingsV2?api-version=2022-03-01"
$authSettings = az rest --method get --url $authSettingsUrl --output json | ConvertFrom-Json
$clientId = $authSettings.properties.identityProviders.azureActiveDirectory.registration.clientId

if ([string]::IsNullOrWhiteSpace($clientId)) {
    throw "Could not resolve the Easy Auth Azure AD client ID for '$appName'."
}

Write-Host "Enabling ID token issuance for app registration $clientId..."
$appRegistration = az ad app show --id $clientId --output json | ConvertFrom-Json
$implicitGrantPatch = @{
    web = @{
        implicitGrantSettings = @{
            enableIdTokenIssuance     = $true
            enableAccessTokenIssuance = $false
        }
    }
} | ConvertTo-Json -Depth 5 -Compress
az rest --method patch --url "https://graph.microsoft.com/v1.0/applications/$($appRegistration.id)" --headers "Content-Type=application/json" --body $implicitGrantPatch | Out-Null

Write-Host "Restarting App Services..."
az webapp restart --resource-group $ResourceGroup --name $appName | Out-Null
az webapp restart --resource-group $ResourceGroup --name $apiName | Out-Null

Write-Host "Application-only deployment completed."
Write-Host "Frontend URL: https://$appName.azurewebsites.net"
Write-Host "API URL: https://$apiName.azurewebsites.net"
