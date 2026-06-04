# Morgan – Test Engineer History

## Phase 3: Semantic Cache & Load Balancing (Issue #38)

**Date:** 2025-07  
**Status:** ✅ Complete — all 23 tests passing, committed `6edc07c`

### Work Delivered

| Artifact | Purpose |
|---|---|
| `src/api/tests/test_phase3_cache_and_resilience.py` | 15 fully-mocked pytest tests |
| `infra/scripts/validate-cache-hit-rate.sh/.ps1` | Live APIM cache hit rate validation (>20% threshold) |
| `infra/scripts/test-failover.sh/.ps1` | Live failover tests (<2s latency, 429 handling) |
| `docs/phase3-roi-report.md` | ROI report template for Issue #38 success criteria |

### Key Decisions Made

1. **Pure-mock test strategy:** Phase 3 tests follow the exact pattern from `test_x_user_id_and_apim.py` — all Azure SDK modules mocked via `sys.modules` before app import. No live Azure calls in CI.

2. **ROI calculator as pure function:** `_calculate_cache_roi()` embedded in test file — no Azure dependency, testable in isolation. Inputs: `(total_requests, cache_hits, cost_per_call, redis_monthly_cost)`.

3. **Header contract verification:** Tests assert backend returns HTTP 200 when APIM injects `X-Cache-Status`, `X-APIM-Backend`, `X-APIM-Version`, `X-RateLimit-Remaining` — confirms backend does not reject APIM-injected headers.

4. **Graceful rate-limit test:** Live failover scripts treat missing 429 as `_info` (not `_fail`) because APIM rate limit policies may be per-product vs per-subscription.

### Test Results

```
23 passed in 54.34s
  8 Phase 2 tests (test_x_user_id_and_apim.py) — no regressions
  15 Phase 3 tests (test_phase3_cache_and_resilience.py) — all new, all green
```

### Patterns Established for Future Phases

- Any new APIM header → add one `test_*_endpoint_accepts_*_header` test
- Any new pure business logic → extract to standalone function, add 3–4 unit tests
- Live validation scripts: always provide both `.sh` (bash) and `.ps1` (PowerShell 7+) variants

---

## Phase 3 Integration Complete (2026-05-31)

All Phase 3 cross-team dependencies validated and documented:
- **Depends on kai:** Redis backend and APIM pool (openai-primary/openai-pool) ✅ Live
- **Depends on alex:** APIM policies (chart-policy.xml + chat-policy.xml) with retry/cache headers ✅ Deployed
- **Delivery:** Validation scripts successfully verify cache hit rates >20% and failover latency <2s

Session status: **COMPLETE**. Orchestration logs recorded. Scribe merge + commit pending.

---

## Dashboard Telemetry Validation (2026-05-31)

**Trigger:** Kai's PR commit `6174afd` described as "fix" to Azure Monitor dashboard  
**Status:** ❌ Root issue NOT fixed — telemetry table mismatch confirmed

### What Was Audited

Fully read all dashboard artifacts (`monitor-dashboard.bicep`, `monitor-dashboard.json`) and all app telemetry code (`event_utils.py`, `api_routes.py`, `chat_service.py`, `azure_openai_helper.py`). Grep-searched entire `src/api` for `CKM-Token`, `track_metric`, `customMetrics`.

### Critical Findings

**Finding 1 — P0:** Dashboard KQL queries `customMetrics | where name startswith "CKM-TokenUsage"`.  
App exclusively uses `track_event()` from `azure.monitor.events.extension` → writes to `customEvents` table.  
`customMetrics` is never written. Tiles 4 (Token Usage Over Time) and 6 (Top Users by Token Consumption) will **always render empty**.

**Finding 2 — P1:** Tile 6 groups by `customDimensions["User ID"]` (space, title-case).  
App emits `"user_id"` (underscore, lowercase) in event payloads. Even if table were correct, user breakdown would always be blank (KQL dimension keys are case-sensitive).

**Finding 3 — INFO:** Commit `6174afd` only compiled Bicep → ARM JSON. No telemetry code changed. The compilation was necessary but not sufficient — the gap predates this commit.

**Finding 4 — PASS:** `monitor-dashboard.json` is internally consistent with `monitor-dashboard.bicep`. No JSON/Bicep divergence risk.

**Finding 5 — PASS:** APIM-native metric tiles (0–3, 5, 7) will render correctly; they do not depend on app telemetry.

**Finding 6 — MEDIUM:** Zero tests validate the telemetry contract (metric name, dimension key, table type). Existing mocks suppress side effects but never assert on emission targets.

### Recommended Remediation

Kai must choose one path:
- **Fix A (add `track_metric` / OTel counter):** Emit `CKM-TokenUsage*` with `{"User ID": user_id_header}` from `chat_service.py` or `api_routes.py` after each OpenAI response
- **Fix B (update dashboard KQL):** Rewrite tiles 4 & 6 to query `customEvents` with `name == "ChatStreamSuccess"` — requires token counts to be added to that event's properties first
- **Fix C (APIM `emit-metric` policy):** Alex adds APIM token counting via `emit-metric` policy — check if APIM can extract token counts from the OpenAI response header

Morgan must add a `test_token_metric_emitted_to_correct_table` test once fix direction is confirmed.

### Decision Filed

`.squad/decisions/inbox/morgan-dashboard-verification.md` — full breakdown with code examples for all three fix options.

**Next Action for Kai:** Read inbox file and choose Fix A, B, or C before Phase 5 dashboard work resumes.
