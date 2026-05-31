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

### 2026-05-31 · Phase 4 Content Safety Architecture (Squad)
- **Adopted:** Azure AI Content Safety via Managed Identity (passwordless) — NOT API key
  - `<authentication-managed-identity resource="https://cognitiveservices.azure.com/" />` in APIM inbound policy
  - Named Value `{{content-safety-endpoint}}` only; no key Named Value exposed
  - APIM system MSI granted `Cognitive Services User` role on Content Safety resource
- **Block threshold:** severity ≥ 4 for all 4 categories (Hate, Violence, Sexual, SelfHarm)
- **Fail-open:** `ignore-error="true"` on `send-request` → if Content Safety unavailable, request is allowed through
- **Audit log headers:** `X-Audit-UserId`, `X-Audit-Timestamp`, `X-Content-Safety-Result` propagated downstream
- **Key Vault:** `kv-callcenter100` stores `apim-subscription-key` + `content-safety-key` (defense-in-depth); APIM uses MSI not KV keys
- **Test coverage:** 34/34 tests passing — `src/api/tests/test_phase4_content_safety.py`
- **Compliance:** `docs/phase4-compliance-evidence.md` — LGPD Art. 46-49, ISO 27001 A.8.24 controls documented
- **Rationale:** MSI eliminates secret rotation burden and removes key exfiltration risk; aligns with LGPD data minimization principle

### 2026-05-31 · Phase 4 Complete — AI Gateway Roadmap (Squad)
- **All 4 phases shipped:**
  - Phase 1 ✅ APIM `apim-callcenter100` + App Insights + logging
  - Phase 2 ✅ Rate limiting (60/min chat, 30/min chart) + `X-User-Id` header propagation
  - Phase 3 ✅ Redis `redis-callcenter100` semantic cache (TTL 5min) + circuit breaker `openai-pool`
  - Phase 4 ✅ Content Safety + audit log + Key Vault + LGPD/ISO 27001 compliance evidence
- **Test count:** 10 (P2) + 15 (P3) + 34 (P4) = 59 gateway tests, all passing
- **Architecture:** `USE_APIM_GATEWAY=true` active; all AI calls route through APIM

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction
