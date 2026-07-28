# Azure Entra ID RBAC Architecture — Conversation Knowledge Mining

## Executive Summary

The application implements role-based access control (RBAC) using Azure Entra ID application roles, integrated with Easy Auth v2 on App Service. In addition, Microsoft Foundry project access is controlled at the project resource scope. The current environment uses these controls:
- **callcenter** — Call center operators (restricted access)
- **faturamento** — Finance/Billing staff (full access)

This document describes the RBAC setup, automation scripts, and deployment workflow.

---

## Architecture Overview

### Components

| Component | Type | Location |
|-----------|------|----------|
| App Registration | Entra ID | ckm-callcenter-app |
| App Roles | Definition | callcenter, faturamento |
| Service Principal | Enterprise App | Automatically created |
| Foundry Access | Azure RBAC | Foundry User on the Foundry account `aif-frx01b002` (user principal + project managed identity) |
| Test Users | Entra ID Users | operador-callcenter@…, financeiro-faturamento@… |
| Easy Auth | App Service | Enabled on both frontend and backend services |
| Role Claims | Token | JWT id_token includes `roles` array |

### Role Definitions

#### **callcenter** — Call Center Operator
- **ID:** `8b9810aa-eef5-493d-8890-8dd16a6cbbcc`
- **Description:** Access to all topics except Billing and Payment Issues
- **Test User:** `operador-callcenter@<tenant>.onmicrosoft.com`
- **Use Case:** Call center staff who handle general inquiries and technical support (no financial data access)

#### **faturamento** — Financeiro/Faturamento
- **ID:** `c8c277ec-cda9-45da-922c-ac1a3c67db38`
- **Description:** Complete access including Billing and Payment Issues
- **Test User:** `financeiro-faturamento@<tenant>.onmicrosoft.com`
- **Use Case:** Finance and billing staff with full access to all topics and payment-related data

### Authentication Flow

```
User Login
    ↓
Easy Auth (/.auth/login/aad)
    ↓ [hybrid flow: code + id_token]
Azure AD → /callback
    ↓ [validates code, issues id_token]
App Service (/.auth/complete)
    ↓ [stores id_token in client cookie]
Browser Cookie
    ↓ [Frontend: Bearer id_token]
API Calls (GET /.auth/me)
    ↓ [Easy Auth extracts roles claim from id_token]
Backend (Authorization header: X-Ms-Client-Principal-Id)
    ↓ [Backend checks token roles and grants/denies access]
Response (Topics filtered by role)
```

---

## RBAC Setup Workflow

### Prerequisites

1. **Azure CLI** — authenticated with permissions to:
   - Create/update App Registrations
   - Create Service Principals
   - Create Entra ID users
   - Assign app roles
   - Configure App Service authentication

2. **Subscription & Resource Group** — Specified in `infra/scripts/rbac-config.json`:
   - Subscription: `a2ec8402-d75b-419c-b71d-7558309c50dc`
   - Resource Group: `rg-callcenter-100`

3. **Linux/macOS (for Bash script)** — `python3` required for JSON processing

### Execution Steps

#### **Step 1: Run RBAC Setup Script** (Choose one platform)

**Windows/PowerShell:**
```powershell
cd infra/scripts
.\setup-entra-id-rbac.ps1
```

**Linux/macOS/Bash:**
```bash
cd infra/scripts
chmod +x setup-entra-id-rbac.sh
./setup-entra-id-rbac.sh
```

**Output:** `infra/scripts/.rbac-output.json` — contains all RBAC metadata (App IDs, role IDs, test user info)

#### **Step 2: Verify RBAC Output**

Inspect `.rbac-output.json` for:
- ✅ `appRegistration.clientId` — unique ID of the app registration
- ✅ `appRoles.callcenter.id` and `appRoles.faturamento.id` — role GUIDs
- ✅ `testUsers[0].userPrincipalName` and `testUsers[1].userPrincipalName` — UPNs created or found
- ✅ `testUsers[1].temporaryPassword` — temporary password for newly created finance user (if any)

#### **Step 3: Configure Easy Auth on App Service**

```powershell
cd infra/scripts
.\configure-easy-auth.ps1
```

This script will:
1. Discover App Services in `rg-callcenter-100`
2. Apply Easy Auth v2 settings: `azureActiveDirectory.clientId`, `azureActiveDirectory.issuer`, etc.
3. Enable ID token issuance (required for role claims)
4. Configure redirect URIs for `/.auth/login/aad/callback`
5. Disable token store on F1/B1 tier (uses client cookies instead)

#### **Step 4: Validate Role Assignment** (Manual portal check or script)

```bash
# List users and their app role assignments
az ad user list --query "[?userPrincipalName.starts_with('operador-') || userPrincipalName.starts_with('financeiro-')]" --output table

# Check app role assignments for a specific user
OPERADOR_ID=$(az ad user show --id "operador-callcenter@<tenant>" --query "id" -o tsv)
az rest --method GET --url "https://graph.microsoft.com/v1.0/users/${OPERADOR_ID}/appRoleAssignments" --output json
```

#### **Step 5: Test Role Claims in Token**

1. Login to the app with `operador-callcenter@…`
2. Visit `https://<app>.azurewebsites.net/.auth/me` — inspect JWT payload for `roles` array
3. Expected: `roles: ["callcenter"]`

Repeat for `financeiro-faturamento@…` — expected: `roles: ["faturamento"]`

---

## Script Internals & Idempotency

### PowerShell Script (`setup-entra-id-rbac.ps1`)

**Key Functions:**

| Function | Purpose |
|----------|---------|
| `Invoke-AzCommand` | Wrapper around `az cli` with error handling and output validation |
| `Invoke-WithRetry` | Exponential backoff retry for transient Graph API failures |
| `Resolve-TenantDomain` | Fetches tenant's default domain via MS Graph |
| `Ensure-AppRole` | Creates or reuses existing app role (idempotent) |
| `Ensure-UserAndRoleAssignment` | Creates/reuses user and assigns role (idempotent) |

**Idempotency Guarantees:**
- ✅ Checks if app registration exists; reuses if found
- ✅ Preserves existing app roles not in {callcenter, faturamento}
- ✅ Updates app roles only if names/descriptions differ
- ✅ Skips user creation if user principal name already exists
- ✅ Skips role assignment if user already has the role

**Output Generation:**
```powershell
$outputObject = @{
    generatedAt = "ISO 8601"
    subscriptionId = "a2ec8402-d75b-419c-b71d-7558309c50dc"
    resourceGroupName = "rg-callcenter-100"
    tenantId = "..."
    tenantDomain = "..."
    appRegistration = @{ displayName, clientId, objectId, servicePrincipalObjectId }
    appRoles = @{ callcenter = @{id, displayName, description}, faturamento = @{...} }
    testUsers = @[ @{displayName, userPrincipalName, objectId, role, created, temporaryPassword} ]
}
```

### Bash Script (`setup-entra-id-rbac.sh`)

**Functional Parity:**
- Uses `az cli` + Python JSON processing to achieve identical behavior
- Mirrors PowerShell logic for app role creation, user creation, and assignment
- Validates `python3` availability at startup (required for JSON processing)
- Uses same hardcoded subscription/RG from lines 4-6

**Cross-Platform Testing:**
Both scripts should produce identical `.rbac-output.json` output when run against the same tenant.

---

## Configuration Management

### Environment Variables (Optional Override)

Both scripts read from hardcoded constants in the source code:

```powershell
# PowerShell
$SubscriptionId = 'a2ec8402-d75b-419c-b71d-7558309c50dc'
$ResourceGroupName = 'rg-callcenter-100'
$AppDisplayName = 'ckm-callcenter-app'
```

```bash
# Bash
SUBSCRIPTION_ID="a2ec8402-d75b-419c-b71d-7558309c50dc"
RESOURCE_GROUP="rg-callcenter-100"
APP_DISPLAY_NAME="ckm-callcenter-app"
```

**To override** (for other environments), either:
1. Edit the scripts directly (not recommended for production)
2. Maintain separate parameter files (future improvement)
3. Add CLI parameters to scripts (future improvement)

### Central Configuration File

**`rbac-config.json`** — Centralized RBAC configuration with:
- Subscription ID
- Resource group name
- App registration details
- Role definitions
- Test user prefixes
- Easy Auth settings
- Metadata and version tracking

This file is **informational** for now; scripts hardcode values. **Future migration:** Load role definitions from this file to reduce duplication.

---

## Troubleshooting

### Issue: "User already exists" error during setup

**Cause:** A test user with the same UPN was created by a previous script run.

**Resolution:** Script automatically detects and reuses existing user. Re-run safely.

### Issue: Role not appearing in JWT token

**Cause:** Role assignment hasn't replicated to token-issuing service or client cached old token.

**Resolution:**
1. Check role assignment in portal: Microsoft Entra ID → Enterprise applications → ckm-callcenter-app → Users and groups
2. Clear browser cache and cookies; perform new login
3. If role is still missing, wait 15 minutes for Graph API propagation

### Issue: User signs in but gets "does not meet the criteria to access this resource"

**Cause:** The user has Entra access but is missing the Microsoft Foundry account role. In this environment, Foundry access also requires the project managed identity to have the same role on the Foundry account.

**Resolution:**
1. Get the Foundry account resource ID:
   ```bash
   az cognitiveservices account show --name aif-frx01b002 --resource-group financeirax01_02-rg --query id -o tsv
   ```
2. Assign the **Foundry User** role at the **account scope** (`/subscriptions/1a9da512-ff96-4210-8de3-81879a5569f5/resourceGroups/financeirax01_02-rg/providers/Microsoft.CognitiveServices/accounts/aif-frx01b002`) to:
   - the user principal who is signing in
   - the project managed identity for `proj-frx01b002`
3. Re-test the sign-in flow with a fresh browser session.

### Issue: Easy Auth returns HTTP 401 on first login

**Cause:** Redirect URI mismatch or ID token issuance not enabled.

**Resolution:**
1. Verify `/.auth/login/aad/callback` is in App Registration → Authentication → Redirect URIs
2. Verify `web.implicitGrantSettings.enableIdTokenIssuance` is `true` (run `configure-easy-auth.ps1` to fix)
3. Check App Service Easy Auth settings: `azureActiveDirectory.clientId` and `issuer` must match app registration

### Issue: "Cannot read property 'roles' in application code"

**Cause:** Backend not extracting role claims from token properly.

**Resolution:**
1. Verify token contains `roles` claim: visit `/.auth/me` and inspect JSON
2. Check backend code calls `get_user_id(request)` from `auth_utils.py`
3. Confirm application uses token's `roles` claim for access control

---

## Security Considerations

### Temporary Passwords
- Scripts generate temporary passwords only for **newly created** users
- Temporary passwords are logged in `.rbac-output.json` (handle securely!)
- Passwords expire after first login (user forced to set new password)
- **Recommendation:** Store `.rbac-output.json` in Key Vault or encrypted storage

### Token Store on F1/B1 Tier
- `tokenStore.enabled: false` is required (no persistent filesystem)
- Sessions stored in client cookies (signed by Easy Auth)
- **Ensure HTTPS only** — cookies transmitted only over TLS

### App Registration Permissions
- Service Principal requires `User.Read.All` for creating test users (Graph permissions)
- Consider restricting to a dedicated automation account in production

### Role ID Stability
- Role IDs in `.rbac-output.json` are persisted; **do not regenerate** roles unless necessary
- Changing role IDs breaks existing role assignments and requires redeployment

---

## Future Improvements

1. **Parameterization:** Make subscription/RG configurable via CLI arguments or config file
2. **Role CRUD:** Add delete/update subcommands to manage roles without full re-provisioning
3. **Batch User Provisioning:** Load test users from CSV or AD sync group
4. **Automated Testing:** Add `test-rbac.sh` to validate role claims programmatically
5. **Key Vault Integration:** Store temporary passwords and RBAC output in Key Vault instead of local JSON
6. **SQL Entra ID Groups:** Create Entra ID groups for each role and sync to SQL Database for row-level security

---

## References

- [Azure Entra ID App Roles Documentation](https://learn.microsoft.com/en-us/azure/active-directory/develop/howto-add-app-roles-in-applications)
- [App Service Easy Auth v2 Documentation](https://learn.microsoft.com/en-us/azure/app-service/configure-authentication-provider-aad)
- [Microsoft Graph App Role Assignments](https://learn.microsoft.com/en-us/graph/api/serviceprincipal-post-approleassignedto)
- [JWT Role Claims in Azure AD](https://learn.microsoft.com/en-us/azure/active-directory/develop/access-tokens)

---

**Generated:** 2026-06-16T11:45:54.241-03:00 | **Author:** Kai (DevOps Engineer)
