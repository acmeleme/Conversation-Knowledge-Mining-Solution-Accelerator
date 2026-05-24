param(
    [string]$ResourceGroup = 'rg-callcenter-100',
    [string[]]$AppNames,
    [string]$ClientId,
    [string]$TenantId,
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

    Invoke-AzCommand -Arguments @(
        'webapp', 'auth', 'update',
        '--resource-group', $ResourceGroup,
        '--name', $appName,
        '--subscription', $SubscriptionId,
        '--enabled', 'true',
        '--action', 'LoginWithAzureActiveDirectory',
        '--aad-client-id', $ClientId,
        '--aad-token-issuer-url', $issuerUrl,
        '--token-store', 'true',
        '--output', 'json'
    ) | Out-Null

    $callbackUri = "https://$($webApp.defaultHostName)/.auth/login/aad/callback"
    $logoutUri = "https://$($webApp.defaultHostName)/.auth/logout/complete"
    $redirectUris.Add($callbackUri)
    $redirectUris.Add($logoutUri)

    Write-Success "Easy Auth habilitado em $appName"
    Write-Host "    Callback URI: $callbackUri" -ForegroundColor White
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
$redirectPatch = @{
    web = @{
        redirectUris = $mergedRedirectUris
    }
} | ConvertTo-Json -Depth 5 -Compress

Write-Info 'Atualizando redirect URIs da App Registration para o fluxo do Easy Auth.'
Invoke-AzCommand -Arguments @(
    'rest',
    '--method', 'PATCH',
    '--url', "https://graph.microsoft.com/v1.0/applications/$($appRegistration.id)",
    '--headers', 'Content-Type=application/json',
    '--body', $redirectPatch,
    '--output', 'json'
) | Out-Null

Write-Host ''
Write-Host '=== Verificação recomendada ===' -ForegroundColor Magenta
Write-Host '1. Acesse o App Service e confirme que Authentication está habilitado.' -ForegroundColor White
Write-Host '2. Faça login com os usuários de teste criados pelo setup.' -ForegroundColor White
Write-Host '3. Inspecione /.auth/me ou o token JWT para validar a claim roles.' -ForegroundColor White
Write-Host '4. Garanta que a aplicação trate faturamento como role superset de callcenter.' -ForegroundColor White
Write-Host ''
Write-Success 'Configuração do Easy Auth concluída.'
