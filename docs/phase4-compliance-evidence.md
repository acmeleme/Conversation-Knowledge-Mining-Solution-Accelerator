# Phase 4 — Compliance Evidence: LGPD / ISO 27001

**Project:** Conversation Knowledge Mining Solution Accelerator  
**Generated:** 2026-05-31  
**Version:** 4.0 (Phase 4)  
**Issue:** [#39](https://github.com/acmeleme/Conversation-Knowledge-Mining-Solution-Accelerator/issues/39)

---

## 1. Content Safety Controls

| Control | Implementation | Status |
|---------|---------------|--------|
| Harmful content blocking | Azure AI Content Safety API (pre-policy in APIM) | ✅ Active |
| Categories monitored | Hate, Violence, Sexual, SelfHarm | ✅ Configured |
| Severity threshold | 4 (blocks severity 4-6, allows 0-3) | ✅ Applied |
| Failure mode | `ignore-error="true"` — safe-fail (allows if CS unavailable) | ✅ Documented |
| Response on block | HTTP 400 + JSON body + X-Content-Safety-Result header | ✅ Active |

## 2. Audit Log

| Field | Source | Destination |
|-------|--------|-------------|
| X-Audit-UserId | X-MS-CLIENT-PRINCIPAL-NAME (Easy Auth) | Response header + App Insights |
| X-Audit-Timestamp | DateTime.UtcNow (ISO 8601) | Response header + App Insights |
| X-Content-Safety-Result | Content Safety API response | Response header + App Insights |
| X-APIM-Request-Id | APIM context.RequestId | Response header |
| X-APIM-Version | Policy version (3.0) | Response header |

## 3. Secret Management

| Secret | Storage | Access |
|--------|---------|--------|
| APIM Subscription Key | Azure Key Vault | APIM Managed Identity |
| Content Safety API Key | Azure Key Vault | APIM Managed Identity |

## 4. Data Retention (LGPD Art. 16)

| Data | Retention | Storage |
|------|-----------|---------|
| APIM request logs | 90 days | Log Analytics Workspace |
| App Insights telemetry | 90 days | Application Insights |
| Content Safety decisions | 90 days (via App Insights) | Application Insights |

## 5. Endpoints Protected

| Endpoint | Rate Limit | Content Safety | Cache |
|----------|-----------|----------------|-------|
| POST /api/chat | 60/min/user | ✅ Enabled | N/A (streaming) |
| POST /api/fetchChartData | 30/min/user | ✅ Enabled | Redis 5min |

## 6. Compliance Coverage

| Requirement | LGPD | ISO 27001 | Status |
|------------|------|-----------|--------|
| Data minimization | Art. 6 | A.8.2 | ✅ Only necessary data logged |
| Access control | Art. 46 | A.9.1 | ✅ Rate limiting + auth |
| Incident detection | Art. 48 | A.16 | ✅ Content Safety blocks + logs |
| Audit trail | Art. 37 | A.12.4 | ✅ Full audit headers |
| Secure communication | Art. 46 | A.14.1 | ✅ HTTPS enforced by APIM |
