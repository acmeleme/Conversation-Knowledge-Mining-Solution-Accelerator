# Squad Decisions

## Active Decisions

### 2026-05-26 · Bug Audit — Full Data Flow (Alex)
- **P0 (Fixed):** ChartFilter.tsx `filteredTopics` crash → changed to `(filtersMeta?.Topic ?? []).filter(...)`
- **P0 (Fixed):** sqldb_service.py `get_db_connection()` silent None return → rewrote with explicit error handling
- **P0 (Fixed):** BUG-04 No Foundry Memory scope exposed → added `tenant_id` and `memory_scope` to `/api/me` endpoint
- **P1 (Tracked):** SQL injection in `fetch_chart_data()` → requires WHERE clause refactor with parameterized queries
- **P2 (Minor):** ChartFilter.tsx `renderMenuList` stale deps → flagged for cleanup
- **P3 (Tracked):** `adjust_processed_data_dates()` runs on every API call → move to startup or cache
- **P3 (Info):** History endpoints send forged `X-Ms-Client-Principal-Id` → low risk in production (Easy Auth overrides)

### 2026-05-26 · Foundry Memory Store Implementation (Alex)
- **Adopted:** Azure AI Foundry Memory Store as additive context layer for chat
- **Architecture:** `FoundryMemoryService` in ChatService; scope from Easy Auth identity; memory updates fire-and-forget after streaming
- **Configuration:** Feature flags through `Config`; SDK floor raised to `azure-ai-projects>=2.0.0`
- **Rationale:** Preserves Cosmos DB history; reuses existing credential pattern; keeps memory optional and safe

### 2026-05-26 · SDD Structure Initialization (Alex)
- **Adopted:** Manual Spec-Driven Development directory structure:
  - `docs/envisioning/` (product vision)
  - `docs/features/` (feature specs)
  - `docs/adr/` (architecture decisions)
  - `docs/plans/` (delivery execution)
  - `.copilot/instructions.md` (agent guidance)
- **Rationale:** Shared documentation anchor; consistent formatting; captures current architecture before drift

### 2026-05-26 · Data Ingestion Strategy for processed_data (Kai)
- **Recommended:** Option A — Seed SQL directly from sample data
  - **Command:** `python infra/scripts/seed_processed_data.py` (uses pyodbc + Azure AD token)
  - **Timeline:** Minutes; no pipeline execution needed
  - **Data:** 851 records from `infra/data/sample_processed_data.json` + key phrases
- **Also fix:** `storageAccount` param bug in `run_process_data_scripts.sh` (latent defect for future runs)
- **Status:** Proposed — awaiting Leme approval

### 2026-05-25 · Memory Store Settings Applied (Kai)
- **Completed:** Azure App Service application settings configured:
  - `AZURE_AI_MEMORY_ENABLED=true`
  - `AZURE_AI_MEMORY_STORE_NAME=memory-store-callcenter100`
  - `AZURE_AI_MEMORY_UPDATE_DELAY_SECONDS=300`
- **Verified:** Settings applied; awaiting next app restart for effect

### 2026-05-28 · Easy Auth Encryption Loop — app-financeirax01 (Kai)
- **Root Cause (P0 Fixed):** F1 Free tier + ephemeral storage caused two compounding failures:
  1. **Ephemeral Encryption Key:** `WEBSITE_AUTH_ENCRYPTION_KEY` was not set; Easy Auth generated random keys at startup. Container spin-down (inactivity, CPU limit, maintenance) creates new key → nonce cookies from old key cannot be decrypted → "We couldn't sign you in"
  2. **Ephemeral Token Store:** `tokenStore.enabled: true` with `WEBSITES_ENABLE_APP_SERVICE_STORAGE=false` caused session tokens to vanish on restart → immediate re-login forced → auth loop
- **Fixes Applied:**
  1. Set stable `WEBSITE_AUTH_ENCRYPTION_KEY` (32-byte base64): survives container restarts
  2. Set `tokenStore.enabled: false`: sessions stored in client cookies (no filesystem dependency)
  3. Verified `azureActiveDirectory.clientId`, `openIdIssuer` v2.0, and `allowedAudiences` are correct
  4. Verified redirect URIs on App Registration include both app and api service callbacks
- **Verified:** Post-fix; `/.auth/login/aad` returns `302 → login.microsoftonline.com` with correct `client_id=35f4b07f-...` ✅
- **Recommendations:** Always set `WEBSITE_AUTH_ENCRYPTION_KEY` on F1/ephemeral storage; upgrade to B1+ for `alwaysOn: true` in production.

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction
