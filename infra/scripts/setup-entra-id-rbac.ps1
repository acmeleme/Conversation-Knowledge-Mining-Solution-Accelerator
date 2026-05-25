# Configures Azure Entra ID App Registration with App Roles for RBAC
# Subscription: a2ec8402-d75b-419c-b71d-7558309c50dc
# Resource Group: rg-callcenter-100

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$SubscriptionId = 'a2ec8402-d75b-419c-b71d-7558309c50dc'
$ResourceGroupName = 'rg-callcenter-100'
$AppDisplayName = 'ckm-callcenter-app'
$OutputPath = Join-Path $PSScriptRoot '.rbac-output.json'
$AppRolesPath = Join-Path $PSScriptRoot '.app-roles.json'

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

function Invoke-WithRetry {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$ScriptBlock,

        [int]$MaxAttempts = 5,
        [int]$DelaySeconds = 5
    )

    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        try {
            return & $ScriptBlock
        }
        catch {
            if ($attempt -eq $MaxAttempts) {
                throw
            }

            Write-Warn "Tentativa $attempt falhou. Nova tentativa em $DelaySeconds segundo(s)."
            Start-Sleep -Seconds $DelaySeconds
        }
    }
}

function New-TemporaryPassword {
    return "Temp!$([guid]::NewGuid().ToString('N').Substring(0, 12))Aa1"
}

function Resolve-TenantDomain {
    $domains = Invoke-AzJson -Arguments @(
        'rest',
        '--method', 'GET',
        '--url', 'https://graph.microsoft.com/v1.0/domains',
        '--output', 'json'
    )

    $defaultDomain = $domains.value | Where-Object { $_.isDefault -eq $true } | Select-Object -First 1
    if ($null -ne $defaultDomain -and -not [string]::IsNullOrWhiteSpace($defaultDomain.id)) {
        return $defaultDomain.id
    }

    $onMicrosoftDomain = $domains.value | Where-Object { $_.id -like '*.onmicrosoft.com' } | Select-Object -First 1
    if ($null -ne $onMicrosoftDomain -and -not [string]::IsNullOrWhiteSpace($onMicrosoftDomain.id)) {
        return $onMicrosoftDomain.id
    }

    throw 'Não foi possível localizar um domínio *.onmicrosoft.com para o tenant atual.'
}

function New-AppRoleDefinition {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value,

        [Parameter(Mandatory = $true)]
        [string]$DisplayName,

        [Parameter(Mandatory = $true)]
        [string]$Description,

        [string]$Id
    )

    if ([string]::IsNullOrWhiteSpace($Id)) {
        $Id = [guid]::NewGuid().Guid
    }

    return [ordered]@{
        allowedMemberTypes = @('User')
        description = $Description
        displayName = $DisplayName
        id = $Id
        isEnabled = $true
        value = $Value
    }
}

function Normalize-AppRoleDefinition {
    param(
        [Parameter(Mandatory = $true)]
        $Role
    )

    return [ordered]@{
        allowedMemberTypes = @($Role.allowedMemberTypes)
        description = $Role.description
        displayName = $Role.displayName
        id = $Role.id
        isEnabled = $Role.isEnabled
        value = $Role.value
    }
}

function Ensure-AppRole {
    param(
        [AllowNull()]
        [AllowEmptyCollection()]
        [object[]]$ExistingRoles = @(),

        [Parameter(Mandatory = $true)]
        [string]$Value,

        [Parameter(Mandatory = $true)]
        [string]$DisplayName,

        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    if ($null -eq $ExistingRoles) {
        $ExistingRoles = @()
    }

    $existingRole = $ExistingRoles | Where-Object { $_.value -eq $Value } | Select-Object -First 1
    $roleId = if ($null -ne $existingRole) { $existingRole.id } else { $null }

    return New-AppRoleDefinition -Value $Value -DisplayName $DisplayName -Description $Description -Id $roleId
}

function Ensure-UserAndRoleAssignment {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DisplayName,

        [Parameter(Mandatory = $true)]
        [string]$UserPrincipalName,

        [Parameter(Mandatory = $true)]
        [string]$RoleValue,

        [Parameter(Mandatory = $true)]
        [string]$RoleId,

        [Parameter(Mandatory = $true)]
        [string]$ServicePrincipalObjectId
    )

    $user = Invoke-AzJson -Arguments @(
        'ad', 'user', 'list',
        '--filter', "userPrincipalName eq '$UserPrincipalName'",
        '--query', '[0]',
        '--output', 'json'
    )

    $created = $false
    $temporaryPassword = $null

    if ($null -eq $user) {
        $temporaryPassword = New-TemporaryPassword
        Write-Info "Criando usuário de teste $UserPrincipalName"
        $user = Invoke-AzJson -Arguments @(
            'ad', 'user', 'create',
            '--display-name', $DisplayName,
            '--user-principal-name', $UserPrincipalName,
            '--password', $temporaryPassword,
            '--force-change-password-next-sign-in', 'true',
            '--output', 'json'
        )
        $created = $true
    }
    else {
        Write-Info "Usuário de teste $UserPrincipalName já existe."
    }

    $assignments = Invoke-AzJson -Arguments @(
        'rest',
        '--method', 'GET',
        '--url', "https://graph.microsoft.com/v1.0/users/$($user.id)/appRoleAssignments",
        '--output', 'json'
    )

    $roleAlreadyAssigned = @($assignments.value | Where-Object {
        $_.resourceId -eq $ServicePrincipalObjectId -and $_.appRoleId -eq $RoleId
    }).Count -gt 0

    if (-not $roleAlreadyAssigned) {
        Write-Info "Associando role '$RoleValue' ao usuário $UserPrincipalName"
        $assignmentBody = @{
            principalId = $user.id
            resourceId = $ServicePrincipalObjectId
            appRoleId = $RoleId
        } | ConvertTo-Json
        $assignmentPath = Join-Path $PSScriptRoot ".app-role-assignment-$($user.id).json"
        $assignmentBody | Set-Content -Path $assignmentPath -Encoding utf8

        try {
            Invoke-WithRetry -ScriptBlock {
                Invoke-AzCommand -Arguments @(
                    'rest',
                    '--method', 'POST',
                    '--url', "https://graph.microsoft.com/v1.0/users/$($user.id)/appRoleAssignments",
                    '--headers', 'Content-Type=application/json',
                    '--body', "@$assignmentPath",
                    '--output', 'json'
                ) | Out-Null
            } | Out-Null
        }
        finally {
            Remove-Item -Path $assignmentPath -ErrorAction SilentlyContinue
        }
    }
    else {
        Write-Info "Role '$RoleValue' já associada a $UserPrincipalName"
    }

    return [ordered]@{
        displayName = $DisplayName
        userPrincipalName = $UserPrincipalName
        objectId = $user.id
        role = $RoleValue
        created = $created
        temporaryPassword = $temporaryPassword
    }
}

Write-Info 'Definindo contexto da assinatura Azure.'
Invoke-AzCommand -Arguments @('account', 'set', '--subscription', $SubscriptionId) | Out-Null

$tenantId = Invoke-AzCommand -Arguments @(
    'account', 'show',
    '--subscription', $SubscriptionId,
    '--query', 'tenantId',
    '--output', 'tsv'
)

$tenantDomain = Resolve-TenantDomain
Write-Success "Tenant resolvido: $tenantDomain"

Write-Info "Validando App Registration '$AppDisplayName'"
$appId = Invoke-AzCommand -Arguments @(
    'ad', 'app', 'list',
    '--display-name', $AppDisplayName,
    '--query', '[0].appId',
    '--output', 'tsv'
)

if ([string]::IsNullOrWhiteSpace($appId)) {
    Write-Info "Criando App Registration '$AppDisplayName'"
    $app = Invoke-AzJson -Arguments @(
        'ad', 'app', 'create',
        '--display-name', $AppDisplayName,
        '--sign-in-audience', 'AzureADMyOrg',
        '--output', 'json'
    )
}
else {
    Write-Info "App Registration '$AppDisplayName' já existe."
    $app = Invoke-AzJson -Arguments @(
        'ad', 'app', 'show',
        '--id', $appId,
        '--output', 'json'
    )
}

$existingRoles = [System.Collections.Generic.List[object]]::new()
if ($null -ne $app.appRoles) {
    foreach ($role in @($app.appRoles)) {
        if ($null -ne $role) {
            $existingRoles.Add($role)
        }
    }
}
$preservedRoles = @($existingRoles | Where-Object { $_.value -notin @('callcenter', 'faturamento') } | ForEach-Object {
    Normalize-AppRoleDefinition -Role $_
})

$callcenterRole = Ensure-AppRole -ExistingRoles $existingRoles -Value 'callcenter' -DisplayName 'Call Center Operator' -Description 'Acesso a todos os tópicos exceto Billing and Payment Issues'
$faturamentoRole = Ensure-AppRole -ExistingRoles $existingRoles -Value 'faturamento' -DisplayName 'Financeiro/Faturamento' -Description 'Acesso completo incluindo Billing and Payment Issues'
$appRolesJson = @($preservedRoles + $callcenterRole + $faturamentoRole) | ConvertTo-Json -Depth 10
$appRolesJson | Set-Content -Path $AppRolesPath -Encoding utf8

Write-Info 'Atualizando App Roles da aplicação.'
Invoke-AzCommand -Arguments @(
    'ad', 'app', 'update',
    '--id', $app.id,
    '--app-roles', "@$AppRolesPath",
    '--output', 'json'
) | Out-Null
Remove-Item -Path $AppRolesPath -ErrorAction SilentlyContinue

# Enable ID token issuance required by App Service Easy Auth v2 (runtime ~2).
# Easy Auth uses a hybrid response_type=code id_token flow; without this setting
# AAD returns error 700054 and the /.auth/login/aad/callback returns HTTP 401.
Write-Info 'Habilitando emissão de ID token (necessário para Easy Auth v2 hybrid flow).'
$implicitGrantPatch = @{
    web = @{
        implicitGrantSettings = @{
            enableIdTokenIssuance     = $true
            enableAccessTokenIssuance = $false
        }
    }
} | ConvertTo-Json -Depth 5 -Compress
$implicitGrantPath = Join-Path $PSScriptRoot '.implicit-grant-patch.json'
$implicitGrantPatch | Set-Content -Path $implicitGrantPath -Encoding utf8 -NoNewline
try {
    Invoke-AzCommand -Arguments @(
        'rest',
        '--method', 'PATCH',
        '--url', "https://graph.microsoft.com/v1.0/applications/$($app.id)",
        '--headers', 'Content-Type=application/json',
        '--body', "@$implicitGrantPath",
        '--output', 'json'
    ) | Out-Null
}
finally {
    Remove-Item -Path $implicitGrantPath -ErrorAction SilentlyContinue
}
Write-Success 'Emissão de ID token habilitada.'

$app = Invoke-AzJson -Arguments @(
    'ad', 'app', 'show',
    '--id', $app.appId,
    '--output', 'json'
)

$callcenterRoleId = ($app.appRoles | Where-Object { $_.value -eq 'callcenter' } | Select-Object -First 1).id
$faturamentoRoleId = ($app.appRoles | Where-Object { $_.value -eq 'faturamento' } | Select-Object -First 1).id
Write-Success 'App Roles configuradas.'

Write-Info 'Validando Service Principal da aplicação.'
$servicePrincipal = Invoke-AzJson -Arguments @(
    'ad', 'sp', 'list',
    '--filter', "appId eq '$($app.appId)'",
    '--query', '[0]',
    '--output', 'json'
)

if ($null -eq $servicePrincipal) {
    Write-Info 'Criando Service Principal.'
    $servicePrincipal = Invoke-AzJson -Arguments @(
        'ad', 'sp', 'create',
        '--id', $app.appId,
        '--output', 'json'
    )
    Start-Sleep -Seconds 10
}
else {
    Write-Info 'Service Principal já existe.'
}

$operatorUser = Ensure-UserAndRoleAssignment -DisplayName 'Operador Call Center' -UserPrincipalName "operador-callcenter@$tenantDomain" -RoleValue 'callcenter' -RoleId $callcenterRoleId -ServicePrincipalObjectId $servicePrincipal.id
$financeUser = Ensure-UserAndRoleAssignment -DisplayName 'Financeiro Faturamento' -UserPrincipalName "financeiro-faturamento@$tenantDomain" -RoleValue 'faturamento' -RoleId $faturamentoRoleId -ServicePrincipalObjectId $servicePrincipal.id

$outputObject = [ordered]@{
    generatedAt = (Get-Date).ToString('o')
    subscriptionId = $SubscriptionId
    resourceGroupName = $ResourceGroupName
    tenantId = $tenantId
    tenantDomain = $tenantDomain
    appRegistration = [ordered]@{
        displayName = $AppDisplayName
        clientId = $app.appId
        objectId = $app.id
        servicePrincipalObjectId = $servicePrincipal.id
    }
    appRoles = [ordered]@{
        callcenter = [ordered]@{
            id = $callcenterRoleId
            displayName = 'Call Center Operator'
            description = 'Acesso a todos os tópicos exceto Billing and Payment Issues'
        }
        faturamento = [ordered]@{
            id = $faturamentoRoleId
            displayName = 'Financeiro/Faturamento'
            description = 'Acesso completo incluindo Billing and Payment Issues'
        }
    }
    testUsers = @($operatorUser, $financeUser)
}

$outputObject | ConvertTo-Json -Depth 8 | Set-Content -Path $OutputPath -Encoding utf8
Write-Success "Arquivo de saída gerado em $OutputPath"

Write-Host ''
Write-Host '=== Próximos passos: Easy Auth no App Service ===' -ForegroundColor Magenta
Write-Host "1. Execute: .\configure-easy-auth.ps1 -ClientId $($app.appId) -TenantId $tenantId" -ForegroundColor White
Write-Host '2. Verifique os redirect URIs adicionados para https://<app>.azurewebsites.net/.auth/login/aad/callback' -ForegroundColor White
Write-Host '3. Em App Service Authentication, confirme Redirect to identity provider e Token Store habilitados.' -ForegroundColor White
Write-Host '4. Valide a claim roles no token JWT dos usuários de teste.' -ForegroundColor White
Write-Host ''
Write-Success "Client ID: $($app.appId)"
Write-Success "Tenant ID: $tenantId"
