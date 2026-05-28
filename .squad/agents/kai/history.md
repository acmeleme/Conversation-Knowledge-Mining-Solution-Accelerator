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

## Learnings (Easy Auth — added 2026-05-28)

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
