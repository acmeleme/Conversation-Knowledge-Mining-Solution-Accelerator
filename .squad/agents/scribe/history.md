# Project Context

- **Project:** Conversation-Knowledge-Mining-Solution-Accelerator
- **Created:** 2026-05-25

## Core Context

Agent Scribe initialized and ready for work.

## Recent Updates

📌 Team initialized on 2026-05-25  
📌 **2026-06-14:** Consolidated APIM alignment batch (Kai infra wiring + Alex behavior review + Morgan validation suite)

## Learnings

- **APIM Integration Pattern:** Opt-in gateway via `enableApimGateway` parameter (default `false`) ensures backward compatibility while enabling new deployments to route through APIM without code changes
- **Dual-Mode Design Resilience:** Both direct (Managed Identity) and APIM (subscription key) paths coexist in `azure_openai_helper.py` with safe-defaulting; guards prevent endpoint/key leakage when APIM disabled
- **Infrastructure as Policy:** All APIM controls (rate limiting, content safety pre-check, caching, audit headers) are Bicep + policy files, not application code — reduces blast radius and enables env-specific tuning
- **Header Propagation Transparency:** Route middleware transparently accepts/forwards APIM headers without special handling; compliance headers (`X-Audit-UserId`, `X-Audit-Timestamp`) always present for LGPD/ISO traceability
- **Test Coverage as Deployment Gate:** 66-test validation suite (config + routing + caching + content safety) provides confidence for production deployment; no identified gaps or regressions
- **Pre-Production Readiness Checklists:** Plain-text app settings (e.g., APIM subscription key) are acceptable for dev but require Key Vault migration before production; cache metrics + block rate monitoring are post-launch activities
- **Batch Consolidation Pattern:** When multiple agents work on related phases, inbox decision records should be merged into a single time-stamped decision entry with per-agent subsections for traceability
