param(
    [Parameter(Mandatory = $true)]
    [string]$ResourceGroup,

    [string]$ImageTag
)

$ErrorActionPreference = 'Stop'

$subscriptionId = $env:AZURE_SUBSCRIPTION_ID
$tenantId = $env:AZURE_TENANT_ID

if ([string]::IsNullOrWhiteSpace($ImageTag)) {
    $ImageTag = "app-only-$(Get-Date -Format yyyyMMddHHmmss)"
}

Write-Host "Deploying application only to resource group: $ResourceGroup"

if (-not [string]::IsNullOrWhiteSpace($subscriptionId)) {
    az account set --subscription $subscriptionId | Out-Null
}

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

$resolvedSubscriptionId = $subscriptionId
if ([string]::IsNullOrWhiteSpace($resolvedSubscriptionId)) {
    $resolvedSubscriptionId = az account show --query id -o tsv
}

if ([string]::IsNullOrWhiteSpace($tenantId)) {
    $tenantId = az account show --query tenantId -o tsv
}

$authSettingsUrl = "https://management.azure.com/subscriptions/$resolvedSubscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.Web/sites/$appName/config/authsettingsV2?api-version=2022-03-01"
$authSettings = az rest --method get --url $authSettingsUrl --output json | ConvertFrom-Json
$clientId = $authSettings.properties.identityProviders.azureActiveDirectory.registration.clientId

if ([string]::IsNullOrWhiteSpace($clientId)) {
    throw "Could not resolve the Easy Auth Azure AD client ID for '$appName'. Run configure-easy-auth.ps1 first."
}

# Ensure loginParameters in authsettingsV2 includes response_type=code id_token.
# Easy Auth v2 uses hybrid flow; without this, id_token is absent from /.auth/me and Bearer auth breaks.
# AADSTS700054 occurs if enableIdTokenIssuance is false on the App Registration regardless of loginParameters,
# but keeping loginParameters aligned avoids id_token disappearing from /.auth/me user_claims.
$aadLogin = $authSettings.properties.identityProviders.azureActiveDirectory.login
$currentParams = if ($null -ne $aadLogin -and $null -ne $aadLogin.loginParameters) { @($aadLogin.loginParameters) } else { @() }
$hasResponseType = @($currentParams | Where-Object { $_ -like 'response_type=*' }).Count -gt 0

if (-not $hasResponseType) {
    Write-Host "Adding response_type=code id_token to Easy Auth loginParameters for $appName..."
    if ($null -eq $authSettings.properties.identityProviders.azureActiveDirectory.login) {
        $authSettings.properties.identityProviders.azureActiveDirectory | Add-Member -NotePropertyName 'login' -NotePropertyValue ([PSCustomObject]@{}) -Force
    }
    $authSettings.properties.identityProviders.azureActiveDirectory.login | Add-Member `
        -NotePropertyName 'loginParameters' `
        -NotePropertyValue @('response_type=code id_token', 'scope=openid profile email offline_access') `
        -Force
    $authPatchJson = $authSettings | ConvertTo-Json -Depth 20 -Compress
    $authPatchPath = Join-Path $PSScriptRoot ".auth-login-params-patch-$appName.json"
    $authPatchJson | Set-Content -Path $authPatchPath -Encoding utf8 -NoNewline
    try {
        az rest --method PUT --url $authSettingsUrl --headers 'Content-Type=application/json' --body "@$authPatchPath" --output json | Out-Null
    } finally {
        Remove-Item -Path $authPatchPath -ErrorAction SilentlyContinue
    }
    Write-Host "loginParameters updated for $appName."
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
$graphPatchResult = az rest --method patch --url "https://graph.microsoft.com/v1.0/applications/$($appRegistration.id)" --headers "Content-Type=application/json" --body $implicitGrantPatch 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Graph PATCH failed — enableIdTokenIssuance NOT set on App Registration $($appRegistration.id)."
    Write-Warning "This WILL cause AADSTS700054 on every login."
    Write-Warning "Fix: grant the principal 'Application.ReadWrite.OwnedBy' on MS Graph, then re-run this script OR configure-easy-auth.ps1."
    throw "Graph PATCH for enableIdTokenIssuance failed. Details: $graphPatchResult"
}
Write-Host "ID token issuance enabled on App Registration $($appRegistration.id)."

Write-Host "Restarting App Services..."
az webapp restart --resource-group $ResourceGroup --name $appName | Out-Null
az webapp restart --resource-group $ResourceGroup --name $apiName | Out-Null

Write-Host "Application-only deployment completed."
Write-Host "Frontend URL: https://$appName.azurewebsites.net"
Write-Host "API URL: https://$apiName.azurewebsites.net"
