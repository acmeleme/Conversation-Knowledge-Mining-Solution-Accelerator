# Morgan – Test Engineer History

## Phase 3: Semantic Cache & Load Balancing (Issue #38)

**Date:** 2025-07  
**Status:** ✅ Complete — all 23 tests passing, committed 6edc07c

### Work Delivered
- src/api/tests/test_phase3_cache_and_resilience.py — 15 fully-mocked pytest tests
- infra/scripts/validate-cache-hit-rate.sh/.ps1 — Live APIM cache hit rate validation (>20% threshold)
- infra/scripts/test-failover.sh/.ps1 — Live failover tests (<2s latency, 429 handling)
- docs/phase3-roi-report.md — ROI report template for Issue #38 success criteria

### Key Decisions Made
1. **Pure-mock test strategy:** Phase 3 tests follow the exact pattern from 	est_x_user_id_and_apim.py
2. **Live validation scripts:** Cache hit rate and failover tests require running system

## Recent Session (2026-06-16)
- Team sync: validated auth, RBAC, and guardrails; noted duplicate /me route

## Session 2026-06-16 — AADSTS700054 Root Cause & Fix

**Error reported:** `AADSTS700054: response_type 'id_token' is not enabled for the application.` — occurs after MFA code entry in Microsoft Authenticator.

### Root Cause
Two bugs in `infra/scripts/deploy-app-only.sh` that caused `enableIdTokenIssuance` to either not be set or not be visible when it failed:

1. **Missing `response_type=code id_token` in `--login-parameters`** (line 150): The script called `az webapp auth microsoft update --login-parameters "scope=openid profile email"` — no `response_type=code id_token`. This stripped the hybrid flow parameter that `configure-easy-auth.ps1` had correctly set on the App Service authsettingsV2. Easy Auth v2 inherently uses hybrid flow, so `enableIdTokenIssuance=true` is always required on the App Registration.

2. **Silent Graph PATCH failure** (line 182): `az rest --method PATCH ... --output none >/dev/null` redirected stdout but the error condition was not caught cleanly. If the CI OIDC service principal lacks `Application.ReadWrite.OwnedBy` on Microsoft Graph, the PATCH fails but the script may continue, leaving `enableIdTokenIssuance=false`.

3. **Python `clientId` extraction** returned `"None"` (string) not empty when clientId was JSON null, bypassing the `if [ -z "$CLIENT_ID" ]` guard and causing `az ad app show --id "None"` to fail.

### Changes Made
- **`deploy-app-only.sh`**: Added `response_type=code id_token` + `offline_access` to loginParameters; replaced one-liner Python with explicit error-handled Python3 heredoc; Graph PATCH now fails loudly (`exit 1`) with actionable error message including the Graph permission requirement.
- **`deploy-app-only.ps1`**: Added loginParameters enforcement (adds `response_type=code id_token` if missing); replaced silent `| Out-Null` Graph PATCH with `$LASTEXITCODE` check and `throw` on failure.
- **`.github/workflows/azure-deploy.yml`**: Added "Validate Easy Auth ID Token Issuance" step after deploy that reads `enableIdTokenIssuance` from the App Registration and fails the job if it's false, documenting the root cause and fix action.

### Learnings
- Easy Auth v2 on App Service **always** uses hybrid flow (`response_type=code id_token`) internally. `enableIdTokenIssuance=true` on the App Registration is **mandatory** — not optional.
- The OIDC service principal used in GitHub Actions needs **Microsoft Graph `Application.ReadWrite.OwnedBy`** (or `.All`) to PATCH App Registration properties. ARM Contributor alone is insufficient.
- `az rest --method PATCH --url https://graph.microsoft.com/...` needs the CLI to acquire a Graph token separately from the ARM token — this is where Graph permission gaps cause failures that can be silent if `>/dev/null` is used.
- `configure-easy-auth.ps1` is the authoritative, comprehensive setup script. Every deployment path (`deploy-app-only.sh/.ps1`, CI workflow) must mirror its App Registration patch or invoke it directly.
- Python `print(None)` outputs the string `"None"`, not empty string — always guard with `if cid else ""` or use `sys.exit(1)` on missing keys.

### Key File Paths
- `infra/scripts/configure-easy-auth.ps1` — canonical Easy Auth setup; call after any deployment that changes App Service / App Registration
- `infra/scripts/deploy-app-only.sh` — CI deployment script (Linux/GitHub Actions)
- `infra/scripts/deploy-app-only.ps1` — local deployment script (Windows/PowerShell)
- `.github/workflows/azure-deploy.yml` — GitHub Actions pipeline; now validates `enableIdTokenIssuance` post-deploy

### Immediate Remediation
Run manually to re-apply all settings including `enableIdTokenIssuance`:
```powershell
.\infra\scripts\configure-easy-auth.ps1 -ResourceGroup rg-callcenter-100
```

