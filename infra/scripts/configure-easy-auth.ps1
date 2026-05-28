param(
    [string]$ResourceGroup = 'rg-callcenter-100',
    [string[]]$AppNames,
    [string]$ClientId,
    [string]$TenantId,
    [string]$EncryptionKey,
    [string]$OutputFile = (Join-Path $PSScriptRoot '.rbac-output.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$SubscriptionId = 'a2ec8402-d75b-419c-b71d-7558309c50dc'

function Write-Info([string]$Message) {
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Success([string]$Message) {
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Warn([string]$Message) {
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Invoke-AzCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $output = & az @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "az $($Arguments -join ' ') failed.`n$($output | Out-String)"
    }

    return ($output | Out-String).Trim()
}

function Invoke-AzJson {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $raw = Invoke-AzCommand -Arguments $Arguments
    if ([string]::IsNullOrWhiteSpace($raw)) {
        return $null
    }

    return $raw | ConvertFrom-Json
}

Write-Info 'Definindo contexto da assinatura Azure.'
Invoke-AzCommand -Arguments @('account', 'set', '--subscription', $SubscriptionId) | Out-Null

if (([string]::IsNullOrWhiteSpace($ClientId) -or [string]::IsNullOrWhiteSpace($TenantId)) -and (Test-Path -LiteralPath $OutputFile)) {
    Write-Info "Carregando client ID e tenant ID de $OutputFile"
    $outputJson = Get-Content -LiteralPath $OutputFile -Raw | ConvertFrom-Json
    if ([string]::IsNullOrWhiteSpace($ClientId)) {
        $ClientId = $outputJson.appRegistration.clientId
    }
    if ([string]::IsNullOrWhiteSpace($TenantId)) {
        $TenantId = $outputJson.tenantId
    }
}

if ([string]::IsNullOrWhiteSpace($ClientId) -or [string]::IsNullOrWhiteSpace($TenantId)) {
    throw 'Informe -ClientId e -TenantId ou execute primeiro setup-entra-id-rbac.ps1 para gerar .rbac-output.json.'
}

$appRegistration = Invoke-AzJson -Arguments @(
    'ad', 'app', 'show',
    '--id', $ClientId,
    '--output', 'json'
)

if ($null -eq $appRegistration) {
    throw "Não foi possível localizar a App Registration com client ID $ClientId"
}

if (-not $AppNames -or @($AppNames).Count -eq 0) {
    $discoveredApps = Invoke-AzJson -Arguments @(
        'webapp', 'list',
        '--resource-group', $ResourceGroup,
        '--subscription', $SubscriptionId,
        '--query', "[?starts_with(name, 'app-') || starts_with(name, 'api-')]",
        '--output', 'json'
    )

    if ($null -eq $discoveredApps -or @($discoveredApps).Count -eq 0) {
        Write-Warn 'Nenhum App Service com prefixo app-/api- encontrado. Usando todos os web apps do resource group.'
        $discoveredApps = Invoke-AzJson -Arguments @(
            'webapp', 'list',
            '--resource-group', $ResourceGroup,
            '--subscription', $SubscriptionId,
            '--output', 'json'
        )
    }

    $AppNames = @($discoveredApps | ForEach-Object { $_.name })
}

if (@($AppNames).Count -eq 0) {
    throw "Nenhum App Service encontrado no resource group $ResourceGroup"
}

$issuerUrl = "https://login.microsoftonline.com/$TenantId/v2.0"
$redirectUris = New-Object System.Collections.Generic.List[string]

foreach ($appName in $AppNames) {
    Write-Info "Configurando Easy Auth para $appName"
    $webApp = Invoke-AzJson -Arguments @(
        'webapp', 'show',
        '--resource-group', $ResourceGroup,
        '--name', $appName,
        '--subscription', $SubscriptionId,
        '--output', 'json'
    )

    # api-* apps use Return401 so cross-domain JS fetch() calls get 401 instead of a redirect.
    # app-* (frontend) apps use RedirectToLoginPage for browser navigation.
    $unauthAction = if ($appName -like 'api-*') { 'Return401' } else { 'RedirectToLoginPage' }

    # WHY WEBSITE_AUTH_ENCRYPTION_KEY: On Free/Shared tier (F1/D1), alwaysOn is not available and
    # containers spin down after inactivity. Easy Auth generates a new ephemeral encryption key on
    # every container restart when this setting is absent. Nonce cookies from pre-restart requests
    # become unreadable with the new key → callback validation fails → "We couldn't sign you in" loop.
    # We preserve any existing key to avoid invalidating active sessions.
    $existingSettings = Invoke-AzJson -Arguments @(
        'webapp', 'config', 'appsettings', 'list',
        '--resource-group', $ResourceGroup,
        '--name', $appName,
        '--subscription', $SubscriptionId,
        '--output', 'json'
    )
    $encKeyExists = @($existingSettings | Where-Object { $_.name -eq 'WEBSITE_AUTH_ENCRYPTION_KEY' }).Count -gt 0

    if (-not $encKeyExists) {
        if (-not [string]::IsNullOrWhiteSpace($EncryptionKey)) {
            $keyToApply = $EncryptionKey
        } else {
            $keyToApply = [Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
        }
        Invoke-AzCommand -Arguments @(
            'webapp', 'config', 'appsettings', 'set',
            '--resource-group', $ResourceGroup,
            '--name', $appName,
            '--subscription', $SubscriptionId,
            '--settings', "WEBSITE_AUTH_ENCRYPTION_KEY=$keyToApply",
            '--output', 'json'
        ) | Out-Null
        Write-Warn "WEBSITE_AUTH_ENCRYPTION_KEY set for $appName. SAVE THIS KEY SECURELY — re-running the script without this key will invalidate all existing sessions."
    } else {
        Write-Info "WEBSITE_AUTH_ENCRYPTION_KEY já existe em $appName — chave preservada."
    }

    Invoke-AzCommand -Arguments @(
        'webapp', 'auth', 'update',
        '--resource-group', $ResourceGroup,
        '--name', $appName,
        '--subscription', $SubscriptionId,
        '--enabled', 'true',
        '--action', 'LoginWithAzureActiveDirectory',
        '--aad-client-id', $ClientId,
        '--aad-token-issuer-url', $issuerUrl,
        '--token-store', 'false',
        '--output', 'json'
    ) | Out-Null

    # Increase nonce expiration to 15 minutes to support forced password-change flows.
    # The default 5-minute window expires before AAD finishes the password change redirect,
    # causing HTTP 401 at /.auth/login/aad/callback.
    $subscriptionId = $SubscriptionId
    $authV2Url = "https://management.azure.com/subscriptions/$subscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.Web/sites/$appName/config/authsettingsV2?api-version=2022-03-01"
    $currentAuthConfig = Invoke-AzJson -Arguments @(
        'rest', '--method', 'GET', '--url', $authV2Url, '--output', 'json'
    )
    $currentAuthConfig.properties.login.nonce.nonceExpirationInterval = "00:15:00"

    # WHY tokenStore.enabled=false: tokenStore.enabled=true writes session tokens to
    # /home/data/.auth/tokens/ on the container filesystem. On Free/Shared tier (or any app
    # with WEBSITES_ENABLE_APP_SERVICE_STORAGE=false), this storage is ephemeral — it is wiped
    # on container restart, causing session loss and immediate redirect loops.
    # With tokenStore disabled, sessions are stored entirely in client cookies (~4KB, sufficient
    # for standard AAD scopes including openid, profile, email, offline_access).
    if ($null -eq $currentAuthConfig.properties.tokenStore) {
        $currentAuthConfig.properties | Add-Member -NotePropertyName 'tokenStore' -NotePropertyValue ([PSCustomObject]@{}) -Force
    }
    $currentAuthConfig.properties.tokenStore.enabled = $false

    # Set unauthenticatedClientAction: api-* apps return 401 so JS fetch() works; frontend apps redirect.
    if ($null -eq $currentAuthConfig.properties.globalValidation) {
        $currentAuthConfig.properties.globalValidation = [PSCustomObject]@{}
    }
    $currentAuthConfig.properties.globalValidation.unauthenticatedClientAction = $unauthAction

    if ($appName -like 'api-*') {
        # Only /health is public; all other routes require a valid Bearer id_token.
        $currentAuthConfig.properties.globalValidation | Add-Member -NotePropertyName 'excludedPaths' -NotePropertyValue @('/health') -Force
    }

    if ($appName -like 'app-*') {
        # Hybrid flow: request both authorization code (for token store) and id_token (for apiFetch Bearer header).
        # Without this, AAD v2 only returns a code and id_token is absent from /.auth/me, breaking cross-domain API calls.
        if ($null -eq $currentAuthConfig.properties.identityProviders.azureActiveDirectory.login) {
            $currentAuthConfig.properties.identityProviders.azureActiveDirectory | Add-Member -NotePropertyName 'login' -NotePropertyValue ([PSCustomObject]@{}) -Force
        }
        $currentAuthConfig.properties.identityProviders.azureActiveDirectory.login | Add-Member `
            -NotePropertyName 'loginParameters' `
            -NotePropertyValue @('response_type=code id_token', 'scope=openid profile email offline_access') `
            -Force
    }
    $authConfigJson = $currentAuthConfig | ConvertTo-Json -Depth 20 -Compress
    $authConfigPath = Join-Path $PSScriptRoot ".auth-nonce-patch-$appName.json"
    $authConfigJson | Set-Content -Path $authConfigPath -Encoding utf8 -NoNewline
    try {
        Invoke-AzCommand -Arguments @(
            'rest', '--method', 'PUT', '--url', $authV2Url,
            '--headers', 'Content-Type=application/json',
            '--body', "@$authConfigPath",
            '--output', 'json'
        ) | Out-Null
    }
    finally {
        Remove-Item -Path $authConfigPath -ErrorAction SilentlyContinue
    }
    Write-Success "Nonce expiration ajustado para 15 minutos em $appName"

    $callbackUri = "https://$($webApp.defaultHostName)/.auth/login/aad/callback"
    $logoutUri = "https://$($webApp.defaultHostName)/.auth/logout/complete"
    $redirectUris.Add($callbackUri)
    $redirectUris.Add($logoutUri)

    Write-Success "Easy Auth habilitado em $appName"
    Write-Host "    Callback URI: $callbackUri" -ForegroundColor White

    # Configure CORS for API apps: allow requests from paired frontend app.
    # App Service platform CORS handles OPTIONS preflight before Easy Auth middleware,
    # ensuring cross-domain fetch() calls succeed without CORS errors.
    if ($appName -like 'api-*') {
        $pairedFrontend = $AppNames | Where-Object { $_ -like 'app-*' } | Select-Object -First 1
        if ($pairedFrontend) {
            $pairedApp = Invoke-AzJson -Arguments @(
                'webapp', 'show',
                '--resource-group', $ResourceGroup,
                '--name', $pairedFrontend,
                '--subscription', $SubscriptionId,
                '--output', 'json'
            )
            $frontendOrigin = "https://$($pairedApp.defaultHostName)"
            Invoke-AzCommand -Arguments @(
                'webapp', 'cors', 'add',
                '--resource-group', $ResourceGroup,
                '--name', $appName,
                '--subscription', $SubscriptionId,
                '--allowed-origins', $frontendOrigin,
                '--output', 'json'
            ) | Out-Null
            Write-Success "CORS configurado em $appName para $frontendOrigin"
        }
    }
}

$currentRedirectUris = @()
$webProperty = $appRegistration.PSObject.Properties['web']
if ($null -ne $webProperty -and $null -ne $webProperty.Value) {
    $redirectProperty = $webProperty.Value.PSObject.Properties['redirectUris']
    if ($null -ne $redirectProperty -and $null -ne $redirectProperty.Value) {
        $currentRedirectUris = @($redirectProperty.Value)
    }
}

$mergedRedirectUris = @($currentRedirectUris + @($redirectUris.ToArray()) | Sort-Object -Unique)

# Enable ID token issuance alongside redirect URIs in a single PATCH.
# App Service Easy Auth v2 uses hybrid flow (response_type=code id_token).
# Without enableIdTokenIssuance=true, AAD returns error 700054 and the callback returns HTTP 401.
$appRegPatch = @{
    web = @{
        redirectUris = $mergedRedirectUris
        implicitGrantSettings = @{
            enableIdTokenIssuance     = $true
            enableAccessTokenIssuance = $false
        }
    }
} | ConvertTo-Json -Depth 5 -Compress

Write-Info 'Atualizando redirect URIs e habilitando ID token na App Registration.'
Invoke-AzCommand -Arguments @(
    'rest',
    '--method', 'PATCH',
    '--url', "https://graph.microsoft.com/v1.0/applications/$($appRegistration.id)",
    '--headers', 'Content-Type=application/json',
    '--body', $appRegPatch,
    '--output', 'json'
) | Out-Null

Write-Host ''
Write-Host '=== Verificação recomendada ===' -ForegroundColor Magenta
Write-Host '1. Acesse o App Service e confirme que Authentication está habilitado.' -ForegroundColor White
Write-Host '2. Faça login com os usuários de teste (incluindo a troca de senha obrigatória na 1ª vez).' -ForegroundColor White
Write-Host '3. Inspecione /.auth/me ou o token JWT para validar a claim roles.' -ForegroundColor White
Write-Host '4. Garanta que a aplicação trate faturamento como role superset de callcenter.' -ForegroundColor White
Write-Host '5. O nonce de login está configurado para 15 min (suporte ao fluxo force-change-password).' -ForegroundColor White
Write-Host '6. Em planos sem alwaysOn (F1/D1), confirme que WEBSITE_AUTH_ENCRYPTION_KEY está configurado para prevenir loops de autenticação após reinicializações do container.' -ForegroundColor White
Write-Host ''
Write-Success 'Configuração do Easy Auth concluída.'
