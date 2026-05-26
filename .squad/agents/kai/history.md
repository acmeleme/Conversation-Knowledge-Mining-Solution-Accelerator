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

## Next Steps
Monitor application behavior to ensure Memory Store integration functions correctly with the configured delay and naming conventions.

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
