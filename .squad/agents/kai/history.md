# Kai's Project History

## Work Completed

### Memory Store Configuration (2026-05-25)
Configured Azure App Service application settings for Memory Store functionality on **app-callcenter100**.

**Details:**
- **App Service Name:** app-callcenter100
- **Resource Group:** rg-callcenter-100
- **Azure Location:** East US 2
- **Service Type:** Linux Container-based App Service

**Settings Applied:**
- `AZURE_AI_MEMORY_ENABLED=true`
- `AZURE_AI_MEMORY_STORE_NAME=memory-store-callcenter100`
- `AZURE_AI_MEMORY_UPDATE_DELAY_SECONDS=300`

**Verification:** ✅ All three settings verified in App Service configuration.

---

### Data Ingestion Diagnosis (2026-05-26)
Performed full diagnostic of why `processed_data` SQL table is empty and the dashboard shows "No topics found".

**Findings:**
| Check | Result |
|-------|--------|
| Azure CLI auth | ✅ Authenticated as `admin@MngEnvMCAP197214.onmicrosoft.com` |
| SQL DB `sqldb-callcenter100` | ✅ Online |
| SQL firewall | ✅ Open (AllowAllWindowsAzureIps + AllowSpecificRange) |
| Key Vault `kv-callcenter100` | ⚠️ Public network access DISABLED — only reachable from private network |
| Managed Identity `id-callcenter100` | ✅ clientId: `b33d1eb1-ef1e-456c-be29-f0cd1d595079` |
| ADLS `stcallcenter100` | ⚠️ HNS enabled, shared key disabled — CLI listing blocked from local machine |
| VNet | ❌ None in `rg-callcenter-100` |
| Deployment script runs | ❌ **NEVER RAN** — no `process_data_scripts` entry in deployment history |
| Local sample data | ✅ `infra/data/` has `audio_data.zip`, `call_transcripts.zip`, `sample_processed_data.json` (851 records) |

**Root Cause:** `run_process_data_scripts.sh` was **never executed** after initial infra deployment on 2026-05-22. The `processed_data` SQL table is empty because the data processing Bicep-based deployment script was never triggered.

**Secondary Bug Found:** `run_process_data_scripts.sh` passes `storageAccount=$storageAccountResourceId` as a parameter to `process_data_scripts.bicep`, but that bicep file does NOT declare a `storageAccount` parameter. This mismatch would cause a deployment failure when the script is finally run.

**Action Plan:**
- **Option A (Fast — seed with sample data):** Insert `infra/data/sample_processed_data.json` (851 records) directly into `processed_data` SQL table — instant result, bypasses AI pipeline
- **Option B (Full pipeline):** Fix `run_process_data_scripts.sh` storageAccount param bug → upload transcripts/audio to ADLS → run `run_process_data_scripts.sh rg-callcenter-100`

## Learnings

1. The project uses `azd` (Azure Developer) environments with multiple deployment configurations:
   - `callcenter100` (primary production environment)
   - `callcenter2` (secondary/test environment)

2. The `callcenter100` environment contains:
   - Resource Group: `rg-callcenter-100` (East US 2)
   - Two App Services:
     - `app-callcenter100` (main web application, Linux container)
     - `api-callcenter100` (API service, Linux container)
   - Azure Container Registry: `ckmcc0522172320.azurecr.io`

3. Memory Store settings are now active for the main application service.

4. **Data ingestion pipeline** (discovered 2026-05-26):
   - `infra/scripts/run_process_data_scripts.sh` → triggers `infra/process_data_scripts.bicep` → runs Azure Deployment Script
   - The deployment script downloads and runs `infra/scripts/process_data_scripts.sh` from GitHub raw URL
   - `process_data_scripts.sh` calls `infra/scripts/index_scripts/04_cu_process_data_new_data.py`
   - Python script reads audio/transcripts from ADLS `stcallcenter100/data/custom_transcripts/` and `/custom_audiodata/`
   - All secrets from Key Vault `kv-callcenter100` (public network access disabled — only reachable from private/Azure context)
   - ADLS `stcallcenter100`: HNS enabled, shared key disabled, key-based auth blocked — needs managed identity
   - `infra/data/sample_processed_data.json` has 851 pre-processed records matching `processed_data` table schema (ConversationId, EndTime, StartTime, Content, summary, satisfied, sentiment, topic, key_phrases, complaint, mined_topic)
   - **Bug in `run_process_data_scripts.sh`:** passes `storageAccount=...` to bicep but `process_data_scripts.bicep` has no such param — would cause deployment failure
   - **Fastest fix:** seed SQL directly from `sample_processed_data.json` (851 records available locally)

---

### Easy Auth Authentication Loop Fix — app-financeirax01 (2026-05-28)

Diagnosed and fixed a persistent Azure AD Easy Auth "We couldn't sign you in" authentication loop on `app-financeirax01.azurewebsites.net`.

**Root Cause:**
The App Service runs on **F1 Free tier** (`asp-financeirax01`, SKU: F1) with `alwaysOn: false` and `WEBSITES_ENABLE_APP_SERVICE_STORAGE: false`. Easy Auth generates an ephemeral per-startup encryption key when `WEBSITE_AUTH_ENCRYPTION_KEY` is not set. When the F1 container spins down from inactivity (~20 min) and restarts, the new encryption key can't decrypt nonce cookies from the previous startup → callback validation fails → "We couldn't sign you in" loop. Additionally, `tokenStore.enabled: true` with ephemeral storage means all session tokens are wiped on restart → session loss → redirect loop.

**False Hypotheses Investigated (all disproved):**
- `runtimeVersion: ~1` + SameSite cookie conflict — disproved: nonce cookie already has `SameSite=None; Secure`
- V1/V2 authsettings conflict — ruled out: Azure ARM blocks writes to V1 when app runs in V2 mode
- Client secret invalid — disproved: `client_credentials` grant returned a valid Bearer token
- `runtimeVersion: ~2` changes OAuth flow — disproved: Linux container apps use `code+id_token` + `form_post` regardless of runtimeVersion

**Fix Applied:**
1. Generated 32-byte random encryption key and set `WEBSITE_AUTH_ENCRYPTION_KEY` app setting → nonce cookies are now decryptable across container restarts
2. Set `tokenStore.enabled: false` in `authsettingsV2` → sessions now stored in client cookies (no filesystem dependency)
3. Restarted App Service to apply both changes

**Verification:** App returned HTTP 401 on `/.auth/me` (correct), HTTP 302 on `/.auth/login/aad` with valid nonce cookie (`SameSite=None; Secure`) — auth flow fully operational.

## Next Steps
Monitor application behavior to ensure Memory Store integration functions correctly with the configured delay and naming conventions.

---

### Phase 3 — APIM AI Gateway: Redis Cache + Backend Pool (2026-06-03)

Deployed Azure Managed Redis as APIM external cache and configured backend pool with circuit breaker for Azure OpenAI.

**Resources deployed:**
- `redis-callcenter100` (Azure Managed Redis, Balanced_B0, centralus, port 10000)
- `databases/default` (Redis 7.4, OSSCluster, AllKeysLRU)
- `apim-callcenter100/caches/default` (APIM external cache → Redis connection string)
- `openai-primary` backend with circuit breaker (3×5xx/60s → open 30s, acceptRetryAfter)
- `openai-pool` backend pool referencing `openai-primary`
- Named values: `redis-host`, `redis-port`
- Policies applied to `fetchChartData-post` (cache + retry) and `chat-post` (pool routing, no retry)

**Bicep modules updated:**
- `infra/modules/redis.bicep` — rewritten from retired Azure Cache for Redis to Azure Managed Redis
- `infra/modules/apim-redis-cache.bicep` — port updated 6380→10000
- `infra/modules/apim-backend-pool.bicep` — circuit breaker on individual backend, not pool

**Reference:** `.squad/decisions/inbox/kai-phase3-redis.md`

## Learnings (Phase 3 — 2026-06-03)

13. **Azure Cache for Redis (ALL tiers) is retiring**
    - `Microsoft.Cache/Redis` (Basic/Standard/Premium) returns `BadRequest: Azure Cache for Redis is retiring`
    - Use `Microsoft.Cache/redisEnterprise` with SKU `Balanced_B0`, `Balanced_B1`, etc.
    - CLI: `az extension add --name redisenterprise`, then `az redisenterprise create/show/database`
    - Port changes from **6380 → 10000** (TLS). Hostname: `{name}.{region}.redis.azure.net`

14. **`publicNetworkAccess` is required for Azure Managed Redis (API 2025-07-01)**
    - Omitting `--public-network-access Enabled` → `BadRequest: 'properties.publicNetworkAccess' is required`
    - Always pass this flag explicitly on `az redisenterprise create`

15. **Azure Managed Redis: access keys disabled by default**
    - New databases set `accessKeysAuthentication: Disabled`
    - APIM external cache uses connection string auth → must run: `az redisenterprise database update --access-keys-auth Enabled`
    - Only after this will `list-keys` provide usable keys for APIM

16. **APIM: `circuitBreaker` NOT supported on Pool-type backends**
    - APIM `2023-09-01-preview` returns: `"CircuitBreaker is not supported for backend pool."`
    - Apply `circuitBreaker` rules to the **individual named backend** (e.g., `openai-primary`)
    - The pool inherits circuit breaker state from its member backends automatically
    - Pool resource must NOT include a `circuitBreaker` block

17. **`az rest --body` Unicode encoding bug**
    - Passing JSON with non-ASCII characters (em dashes, special chars) directly as `--body '...'` corrupts the payload
    - Fix: write JSON with `Out-File -FilePath ... -Encoding utf8`, then use `--body "@filepath"`
    - Required for ALL `az rest` calls whose body contains special characters

18. **APIM retry policy breaks SSE / chunked streaming**
    - For streaming endpoints (chat, SSE), do NOT add `<retry>` in the backend policy section
    - Retry buffers the response, breaking `Transfer-Encoding: chunked` and SSE event delivery
    - Use `<forward-request buffer-request-body="false" timeout="120" />` for streaming routes
    - Retry is safe for non-streaming JSON endpoints (e.g., `fetchChartData`)

19. **APIM caches API version: `2023-05-01-preview`**
    - External cache resource (`caches/default`) requires preview API version
    - `useFromLocation: 'default'` sets the cache as global (applies to all regions)
    - APIM auto-stores the connection string as a masked named value (`{{hexid}}`) — normal behavior

20. **Azure Managed Redis race condition on create**
    - If `az redisenterprise create` fails mid-flight, cluster may already be partially created
    - Retry will return `Conflict: The cluster is not yet running.`
    - Fix: poll with `az redisenterprise show --query properties.provisioningState` until `Succeeded`, then proceed normally

5. **F1 Free tier + Easy Auth = ephemeral encryption key (critical)**
   - `WEBSITE_AUTH_ENCRYPTION_KEY` must ALWAYS be set explicitly on Free/Shared tier apps
   - Without it, Easy Auth generates a new random key each container startup
   - Any in-flight auth nonce from before the restart becomes unreadable → auth loop
   - Fix: generate a stable key with `[Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))` and set as an app setting

6. **`WEBSITES_ENABLE_APP_SERVICE_STORAGE=false` + `tokenStore.enabled=true` = session data loss**
   - When storage is ephemeral (container image filesystem), Easy Auth token store writes to `/home/data/.auth/tokens/` but those files vanish on container restart
   - Fix: set `tokenStore.enabled: false` in `authsettingsV2` — session info moves entirely to client cookies (~4KB limit, sufficient for standard AAD scopes)

7. **`runtimeVersion` in authsettingsV2 does NOT control OAuth flow**
   - `platform.runtimeVersion` controls which build of the Easy Auth MODULE runs, not which response_type/response_mode is used
   - Linux container apps always use `response_type=code+id_token` + `response_mode=form_post` (hybrid flow)
   - Changing runtimeVersion from `~1` to `~2` is harmless but has no effect on authentication behavior for Linux containers

8. **V1 authsettings are read-only when `configVersion: v2` is set**
   - Azure ARM rejects writes to `/config/authsettings` with: *"Cannot execute the request because the site is running on auth version v2."*
   - `enabled: true` in V1 config is a legacy artifact that the runtime ignores in V2 mode — not a bug

9. **Nonce cookie `SameSite=None; Secure` is already correct in Easy Auth**
   - Easy Auth automatically sets `SameSite=None` on the nonce cookie to allow cross-site POST from `form_post` callbacks
   - SameSite is NOT a factor in Easy Auth login loops — confirm by inspecting cookie headers before escalating

10. **Diagnosing Easy Auth loops: check these first**
    1. Is `WEBSITE_AUTH_ENCRYPTION_KEY` set? (most common cause on Free tier)
    2. Is `WEBSITES_ENABLE_APP_SERVICE_STORAGE=false`? If so, disable `tokenStore.enabled`
    3. Is the client secret still valid? Test with `client_credentials` grant
    4. Are redirect URIs exactly correct (including trailing slashes)?
    5. Is `signInAudience` correct? `AzureADMyOrg` requires users to be in the same tenant

---

### Volume Conversation Scripts (2026-05-26)
Created two Python scripts + requirements file for generating 500 call-center conversations at volume.

**Files created in `foundry-workflow/`:**
| File | Purpose |
|------|---------|
| `generate_conversations.py` | Sends 500 questions to `CallCenterInsightWorkflow` via azure-ai-projects SDK |
| `generate_chat_conversations.py` | Sends 500 questions to frontend chat API via httpx (async) |
| `requirements_volume.txt` | Dependencies: httpx, tqdm, azure-ai-projects, azure-identity |
| `results/workflow_conversations.json` | Output of Foundry script (created at runtime) |
| `results/chat_conversations.json` | Output of frontend script (created at runtime) |

**Key configuration constants:**
- `ENDPOINT` = `https://aif-callcenter100.services.ai.azure.com/api/projects/proj-callcenter100`
- `FRONTEND_URL` = `https://app-callcenter100.azurewebsites.net` (configurable at top of file)
- `MAX_CONCURRENT` = 10 (asyncio Semaphore)
- `MAX_RETRIES` = 2

**Question bank:** 100 seed templates across 7 categories (billing, technical, activation, account, network, cancellation, upgrades) with substitution variables → 500 unique questions per run.

---

## Cross-Agent Update (2026-05-26)

Scribe processed `.squad/decisions/inbox/` and consolidated decision entries, including Kai's data ingestion recommendation. The data ingestion options (Option A: seed from sample data; Option B: fix pipeline + full run) are now formally recorded in `.squad/decisions.md`. Data ingestion decision marked as **proposed — awaiting Leme approval**.

---

### Easy Auth Verification — app-financeirax01 (2026-05-28)

Post-fix verification of all Easy Auth settings on `app-financeirax01`. All checks PASSED.

**Checks performed:**

| Check | Result | Detail |
|-------|--------|--------|
| `WEBSITE_AUTH_ENCRYPTION_KEY` | ✅ Present | `WNZZGn+PeoOyN4u6HRztjFW7718jMpVcB1/T5n/AZ5M=` (32-byte base64) |
| `tokenStore.enabled` | ✅ False | Sessions stored in client cookies — no filesystem dependency |
| Easy Auth enabled | ✅ True | `platform.enabled: true`, `runtimeVersion: ~2` |
| clientId | ✅ Correct | `35f4b07f-cee7-46d7-8193-906d1dc961b1` |
| openIdIssuer | ✅ Correct | `https://login.microsoftonline.com/2e50c5c4-.../v2.0` |
| allowedAudiences | ✅ Both set | `35f4b07f-...` AND `api://35f4b07f-...` |
| `/.auth/login/aad` | ✅ 302→AAD | Redirects to `login.microsoftonline.com` with correct `client_id` |
| `/.auth/me` (unauthenticated) | ✅ 302→Login | Expected: `unauthenticatedClientAction=RedirectToLoginPage` |

**Note on `/.auth/me` returning 302 vs 401:**  
The app is configured with `globalValidation.unauthenticatedClientAction: "RedirectToLoginPage"`, which redirects ALL unauthenticated requests — including `/.auth/me` — to the login page. This is correct behavior. If `unauthenticatedClientAction` were `"Return401"`, then `/.auth/me` would return 401. Both indicate Easy Auth is working properly.

**Learnings (added 2026-05-28):**

11. **`unauthenticatedClientAction` affects `/.auth/me` response code**
    - `"RedirectToLoginPage"` → `/.auth/me` returns 302 (unauthenticated requests redirected to login)
    - `"Return401"` or `"Return403"` → `/.auth/me` returns 401/403
    - Both are valid; 302 from `/.auth/me` does NOT indicate a problem when `RedirectToLoginPage` is set

12. **`configure-easy-auth.ps1` is now idempotent for Free-tier encryption key and token store**
    - Added `-EncryptionKey` optional parameter; if omitted, a 32-byte random key is generated on first run
    - Script checks `WEBSITE_AUTH_ENCRYPTION_KEY` existence before writing — preserves a stable key across re-runs
    - `--token-store false` passed to `az webapp auth update` and `tokenStore.enabled = false` set in authsettingsV2 PUT body
    - Both changes together prevent the F1 auth loop: stable nonce encryption + no filesystem session dependency
    - Comment blocks added inline explaining WHY each setting is required (F1 restart scenario)
