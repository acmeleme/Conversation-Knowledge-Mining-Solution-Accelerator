# Kai's Project History

## Work Completed (Condensed)

### Memory Store Configuration (2026-05-25)
Configured Azure App Service (`app-callcenter100`, East US 2) with Memory Store settings: `AZURE_AI_MEMORY_ENABLED=true`, `AZURE_AI_MEMORY_STORE_NAME=memory-store-callcenter100`, `AZURE_AI_MEMORY_UPDATE_DELAY_SECONDS=300`. ✅ Verified.

### Data Ingestion Diagnosis (2026-05-26)
Diagnosed empty `processed_data` SQL table. **Root cause:** `run_process_data_scripts.sh` was never executed after 2026-05-22 infra deployment. **Secondary bug:** script passes `storageAccount` parameter to bicep file that doesn't declare it (deployment would fail).

**Options:** (A) Fast—seed SQL from `infra/data/sample_processed_data.json` (851 records); (B) Full—fix param bug, upload to ADLS, run pipeline. **Key findings:** ADLS `stcallcenter100` has HNS + key auth disabled (needs managed identity); Key Vault public network access disabled.

### Easy Auth Authentication Loop Fix — app-financeirax01 (2026-05-28)
**Root cause:** F1 Free tier + `WEBSITE_AUTH_ENCRYPTION_KEY` unset → ephemeral encryption key on container restart → nonce cookie unreadable → auth loop. **Fix:** (1) Generated 32-byte encryption key, set app setting; (2) Set `tokenStore.enabled: false` (session → client cookies). ✅ Verified—auth flow operational.

### Easy Auth Verification (2026-05-28)
Post-fix audit of `app-financeirax01` completed. All checks passed: encryption key present, token store disabled, Easy Auth enabled, clientId/issuer correct, `/.auth/login/aad` returns 302→AAD, `/.auth/me` correctly returns 302 (redirects unauthenticated requests per config).

### Volume Conversation Scripts (2026-05-26)
Created Python scripts for generating 500 call-center conversations at volume:
- `generate_conversations.py` — Sends 500 questions to CallCenterInsightWorkflow via azure-ai-projects SDK
- `generate_chat_conversations.py` — Sends 500 questions to frontend chat API via httpx (async, 10 concurrent, 2 retries)
- 100 seed question templates across 7 categories (billing, technical, activation, account, network, cancellation, upgrades)

### Phase 3 — APIM AI Gateway: Redis Cache + Backend Pool (2026-06-03)
Deployed Azure Managed Redis (`redis-callcenter100`, Balanced_B0, centralus, port 10000) as APIM external cache with circuit breaker on OpenAI backend. Bicep modules updated: `redis.bicep` (retired Azure Cache for Redis → Managed Redis), `apim-redis-cache.bicep` (port 6380→10000), `apim-backend-pool.bicep` (circuit breaker on individual backend, not pool).

### Phase 4 — Content Safety + Key Vault + APIM Named Values (2026-05-31)
Provisioned Azure AI Content Safety (`contentsafety-callcenter100`, S0, centralus) and integrated APIM with Content Safety using managed identity authentication. Reused existing Key Vault (`kv-callcenter100`) in RBAC mode, stored `apim-subscription-key` and `content-safety-key` as ARM-managed secrets, granted APIM `Key Vault Secrets User`, and added APIM named values `content-safety-endpoint` + `content-safety-key` (Key Vault reference). Updated APIM operation policies for `chat-post` and `fetchChartData-post` and added Bicep modules `content-safety.bicep` + `keyvault.bicep`.

## Learnings

1. **azd environments:** Callcenter100 (primary, East US 2) + Callcenter2 (test). Resources: RG `rg-callcenter-100`, App Services `app-callcenter100` + `api-callcenter100` (Linux containers), ACR `ckmcc0522172320.azurecr.io`.

2. **Memory Store:** Settings now active for main application service.

3. **Data ingestion pipeline:** `run_process_data_scripts.sh` → `process_data_scripts.bicep` → Azure Deployment Script → `process_data_scripts.sh` → `04_cu_process_data_new_data.py`. Reads from ADLS (`stcallcenter100/data/custom_transcripts/` + `/custom_audiodata/`), secrets from Key Vault, outputs to `processed_data` SQL table.

4. **ADLS configuration:** HNS enabled, shared key disabled, key-based auth blocked — requires managed identity (`id-callcenter100`, clientId: `b33d1eb1-ef1e-456c-be29-f0cd1d595079`).

5. **F1 Free tier + Easy Auth = ephemeral encryption key (critical).** `WEBSITE_AUTH_ENCRYPTION_KEY` must be set explicitly. Without it, Easy Auth generates a new random key each startup → nonce cookies unreadable after restart → auth loop. **Fix:** generate stable 32-byte key, set as app setting.

6. **`WEBSITES_ENABLE_APP_SERVICE_STORAGE=false` + `tokenStore.enabled=true` = session data loss.** Token store writes to `/home/data/.auth/tokens/` which vanishes on container restart. **Fix:** set `tokenStore.enabled: false` → session info moves to client cookies (~4KB, sufficient for standard AAD scopes).

7. **`runtimeVersion` in authsettingsV2 does NOT control OAuth flow.** Runtimeversion controls which Easy Auth MODULE runs; Linux container apps always use `response_type=code+id_token` + `response_mode=form_post` (hybrid flow). Changing runtimeVersion has no effect on authentication behavior.

8. **V1 authsettings are read-only when `configVersion: v2` is set.** Azure ARM rejects writes to `/config/authsettings` with error: *"Cannot execute the request because the site is running on auth version v2."* V1 `enabled: true` is legacy artifact ignored by runtime in V2 mode.

9. **Nonce cookie `SameSite=None; Secure` is already correct in Easy Auth.** Easy Auth auto-sets SameSite=None to allow cross-site POST from form_post callbacks. SameSite is NOT a factor in Easy Auth login loops.

10. **Diagnosing Easy Auth loops: check these first:**
    1. Is `WEBSITE_AUTH_ENCRYPTION_KEY` set? (most common cause on Free tier)
    2. Is `WEBSITES_ENABLE_APP_SERVICE_STORAGE=false`? If so, disable `tokenStore.enabled`
    3. Is the client secret still valid? Test with `client_credentials` grant
    4. Are redirect URIs exactly correct (including trailing slashes)?
    5. Is `signInAudience` correct? `AzureADMyOrg` requires users to be in the same tenant

13. **Azure Cache for Redis (ALL tiers) is retiring.** Use `Microsoft.Cache/redisEnterprise` with SKU `Balanced_B0`, `Balanced_B1`, etc. CLI: `az extension add --name redisenterprise`. Port: **6380 → 10000** (TLS).

14. **`publicNetworkAccess` is required for Azure Managed Redis (API 2025-07-01).** Omitting `--public-network-access Enabled` → `BadRequest: 'properties.publicNetworkAccess' is required`.

15. **Azure Managed Redis: access keys disabled by default.** New databases set `accessKeysAuthentication: Disabled`. For APIM external cache (connection string auth), run: `az redisenterprise database update --access-keys-auth Enabled`.

16. **APIM: `circuitBreaker` NOT supported on Pool-type backends.** Returns: *"CircuitBreaker is not supported for backend pool."* Apply `circuitBreaker` rules to the **individual named backend** (e.g., `openai-primary`). Pool inherits circuit breaker state automatically.

17. **`az rest --body` Unicode encoding bug.** Passing JSON with non-ASCII characters (em dashes, special chars) directly as `--body '...'` corrupts payload. **Fix:** write JSON with `Out-File -FilePath ... -Encoding utf8`, then use `--body "@filepath"`.

18. **APIM retry policy breaks SSE / chunked streaming.** For streaming endpoints (chat, SSE), do NOT add `<retry>` in backend policy section. Retry buffers response, breaking `Transfer-Encoding: chunked` and SSE event delivery. Use `<forward-request buffer-request-body="false" timeout="120" />` for streaming routes; retry safe for non-streaming JSON endpoints.

19. **APIM caches API version: `2023-05-01-preview`.** External cache resource (`caches/default`) requires preview API version. `useFromLocation: 'default'` sets cache as global (applies to all regions). APIM auto-stores connection string as masked named value—normal behavior.

20. **Azure Managed Redis race condition on create.** If `az redisenterprise create` fails mid-flight, cluster may be partially created. Retry returns `Conflict: The cluster is not yet running.` **Fix:** poll with `az redisenterprise show --query properties.provisioningState` until `Succeeded`, then proceed.
21. **Content Safety keys can still be retrieved through ARM `listKeys` even when CLI `account keys list` is blocked by `disableLocalAuth=true`.** Use `POST .../accounts/{name}/listKeys?api-version=2023-05-01` with `az rest` when the service is policy-enforced.
22. **Existing Key Vault may be RBAC-only + public network disabled.** In that case, `az keyvault set-policy` and `az keyvault secret set` can fail from a developer workstation. Use ARM-managed `Microsoft.KeyVault/vaults/secrets` resources for secret creation and grant APIM `Key Vault Secrets User` via RBAC.
23. **APIM `send-request` can call Content Safety with managed identity.** Inside policy use `<authentication-managed-identity resource="https://cognitiveservices.azure.com/" />` and omit `client-id`; APIM injects the bearer token for the outbound request.

11. **`unauthenticatedClientAction` affects `/.auth/me` response code.** `"RedirectToLoginPage"` → 302; `"Return401"`/`"Return403"` → 401/403. Both indicate Easy Auth working properly; 302 is NOT a bug when RedirectToLoginPage is set.

12. **`configure-easy-auth.ps1` is now idempotent for Free-tier encryption key and token store.** Script generates 32-byte key on first run, preserves across re-runs. Sets `--token-store false` + `tokenStore.enabled = false`. Both together prevent F1 auth loop: stable nonce encryption + no filesystem session dependency.

## Cross-Agent Updates

**2026-05-26:** Scribe consolidated decision entries including Kai's data ingestion recommendation. Data ingestion options (A: seed from sample; B: fix pipeline + full run) now formally recorded in `.squad/decisions.md`. Awaiting approval.

## Phase 3 Completion & Cross-Agent Integration (2026-05-31)

Phase 3 session finalized. Kai's Redis infrastructure, Alex's APIM policies, and Morgan's validation tests all integrated successfully:
- **Redis backend:** redis-callcenter100 (Balanced_B0, Central US) serving APIM cache @ TTL 5min
- **APIM pool:** openai-primary + openai-pool with 3-failure circuit breaker active
- **Policies deployed:** chart-policy.xml (cache + retry), chat-policy.xml (pool routing)
- **Validation:** 15 unit tests + 2 failover scripts (validate-cache-hit-rate, test-failover)

All cross-agent dependencies satisfied. Session status: **COMPLETE**.
