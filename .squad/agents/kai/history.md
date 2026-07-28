# Kai's Project History

## Work Completed (Condensed)

### Memory Store Configuration (2026-05-25)
Configured Azure App Service (East US 2) with Memory Store settings: AZURE_AI_MEMORY_ENABLED=true, AZURE_AI_MEMORY_UPDATE_DELAY_SECONDS=300. ✅ Verified.

### Easy Auth Authentication Loop Fix — app-financeirax01 (2026-05-28)
**Root cause:** F1 Free tier + WEBSITE_AUTH_ENCRYPTION_KEY unset → ephemeral encryption key on container restart → nonce cookie unreadable → auth loop. **Fix:** (1) Generated 32-byte encryption key, set app setting; (2) Set 	okenStore.enabled: false (session → client cookies). ✅ Verified—auth flow operational.

### Easy Auth Verification (2026-05-28)
Post-fix audit of pp-financeirax01 completed. All checks passed: encryption key present, token store disabled, Easy Auth enabled, clientId/issuer correct, /.auth/login/aad returns 302→AAD, /.auth/me correctly returns 302 (redirects unauthenticated requests per config).

## Recent Session (2026-06-16)
- Team sync: auth/RBAC/guardrails decisions merged and consolidated

## Learnings

### Callback DNS Error — Client-Side DNS Failure, Not Azure Issue (2026-06-16)
**Environment:** financeirax0102 — `app-frx01b002.azurewebsites.net`
**Symptom:** User browser shows "Hmmm… can't reach this page — server IP address could not be found" at `/.auth/login/aad/callback` after AAD login.
**Diagnosis:**
- App Service: Running, availabilityState=Normal, publicNetworkAccess=Enabled, B1 plan ✅
- App Registration `ckm-frx01b002-easyauth` (`cddb0f0e`): redirect URIs correct, enableIdTokenIssuance=true ✅
- Easy Auth authsettingsV2: correct clientId, issuer v2.0, response_type=code id_token, tokenStore=false ✅
- Direct IP test (13.89.172.3): `/` → HTTP 401 (Easy Auth intercepting), `/.auth/login/aad` → 302 to AAD ✅
- `nslookup app-frx01b002.azurewebsites.net 8.8.8.8` → resolves to 13.89.172.3 ✅
- System DNS (`[System.Net.Dns]::GetHostAddresses()`, curl, browser): "No such host is known" ❌
**Root cause:** Azure infrastructure is healthy. DNS failure is CLIENT-SIDE — the local network/DNS resolver (home router or corporate DNS) fails to resolve `app-frx01b002.azurewebsites.net` even though public DNS (8.8.8.8) resolves it fine.
**Fix for user:**
  1. Run `ipconfig /flushdns` to clear negative DNS cache
  2. Try from a different network or mobile hotspot
  3. If on VPN, disconnect/reconnect
  4. Temporary hosts entry: `13.89.172.3 app-frx01b002.azurewebsites.net`
**Pattern:** When callback URL shows DNS error but App Service shows Running in Azure portal, always verify via direct IP first (`nslookup hostname 8.8.8.8` + `curl --connect-to`). If direct IP works, the problem is on the client, not Azure. If direct IP also fails, then investigate container crash loop, ACR pull failure, or App Service plan exhaustion.

### AADSTS700054 Root Cause — Wrong App Registration for Easy Auth (2026-06-16)
**Environment:** financeirax0102 (sub `1a9da512`, rg `financeirax01_02-rg`, apps `app-frx01b002`/`api-frx01b002`)
**Root cause:** Easy Auth on `app-frx01b002` was pointing to the AI Foundry auto-generated App Registration (`aif-frx01b002-proj-frx01b002-AgentIdentityBlueprint`, clientId `cae02aad-7034-46cf-b046-623034c2bd47`). That App Registration:
  1. Had `enableIdTokenIssuance = false` → AADSTS700054 error after MFA
  2. Had no redirect URIs registered
  3. Had no `response_type=code id_token` loginParameters set in authsettingsV2
  4. Was owned by a Managed Identity (AI Foundry) → could NOT be patched by regular admin user (Insufficient privileges)
**Fix:** Created dedicated App Registration `ckm-frx01b002-easyauth` (clientId `cddb0f0e-f6f2-4288-ac36-2e023eb068b8`), enabled `enableIdTokenIssuance=true`, registered redirect/logout URIs, configured authsettingsV2 with `response_type=code id_token`, tokenStore=false, nonce 15min, WEBSITE_AUTH_ENCRYPTION_KEY. ✅ Verified and restarted.
**Pattern:** AI Foundry creates its own App Registration (named `AgentIdentityBlueprint`) for internal use. NEVER use this for Easy Auth — always create a separate dedicated App Registration.
**Key file path:** `infra/scripts/configure-easy-auth.ps1` already has the full fix pattern; the issue was it was never run for this env, and even if run, it would have failed to patch the AI Foundry app reg.
