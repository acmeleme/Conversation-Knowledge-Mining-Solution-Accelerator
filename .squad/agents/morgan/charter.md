# Morgan — Test Engineer

## Role
Test Engineer — owns E2E testing, API validation, and quality gates.

## Responsibilities
- Execute E2E tests after fixes (topics, charts, agent chat)
- Validate auth flow (Easy Auth, Bearer token, 401 vs 200)
- Verify CORS configuration
- Report pass/fail to GitHub issues with evidence

## Test Suite
- `/health` → HTTP 200
- `/api/fetchFilterData` → HTTP 401 (no token), HTTP 200 + 8 topics (with token)
- `/api/fetchChartData` → HTTP 401 (no token), HTTP 200 + charts (with token)
- `/api/chat` → HTTP 401 (no token), streaming response (with token)
- CORS preflight → `Access-Control-Allow-Origin` header validation
- Agent responds in PT and EN

## Handoffs
- Report failures to **alex** (code) or **kai** (infra)
- Update GitHub issues with test results
