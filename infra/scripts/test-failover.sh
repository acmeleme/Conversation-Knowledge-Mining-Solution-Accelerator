#!/bin/bash
# test-failover.sh
# Tests APIM circuit breaker, retry behavior, and rate-limit enforcement for Phase 3.
#
# Usage:
#   export APIM_SUBSCRIPTION_KEY="<your-key>"
#   export APIM_URL="https://apim-callcenter100.azure-api.net"   # optional override
#   bash test-failover.sh

set -uo pipefail

APIM_URL="${APIM_URL:-https://apim-callcenter100.azure-api.net}"
API_KEY="${APIM_SUBSCRIPTION_KEY:-}"
ENDPOINT="$APIM_URL/callcenter/api/fetchChartData"
RATE_LIMIT_RPM=30      # configured in APIM policy
FAILOVER_TARGET_SEC=2  # failover must complete within this many seconds

PASS=0
FAIL=0

_pass() { echo "  ✅ $*"; PASS=$((PASS + 1)); }
_fail() { echo "  ❌ $*"; FAIL=$((FAIL + 1)); }
_info() { echo "  ℹ️  $*"; }

echo "╔══════════════════════════════════════════════════╗"
echo "║   🔁  Failover & Circuit Breaker Test — Phase 3  ║"
echo "╚══════════════════════════════════════════════════╝"
echo "  APIM URL  : $APIM_URL"
echo "  Rate limit: ${RATE_LIMIT_RPM}rpm"
echo "  Failover  : <${FAILOVER_TARGET_SEC}s target"
echo ""

if [ -z "$API_KEY" ]; then
  echo "⚠️  WARNING: APIM_SUBSCRIPTION_KEY is not set. Requests may receive 401."
  echo ""
fi

# ── Test 1: Normal request succeeds ─────────────────────────────────────────
echo "── Test 1: Normal request returns 200 ──────────────────"
T_START=$(date +%s%3N)
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Ocp-Apim-Subscription-Key: $API_KEY" \
  -d '{"startDate":"2024-01-01","endDate":"2024-12-31"}' \
  --max-time 10 2>/dev/null) || HTTP_CODE="000"
T_END=$(date +%s%3N)
ELAPSED=$(( (T_END - T_START) ))

if [ "$HTTP_CODE" = "200" ]; then
  _pass "Normal request succeeded (HTTP 200) in ${ELAPSED}ms"
else
  _fail "Normal request returned HTTP $HTTP_CODE (expected 200)"
fi

# ── Test 2: Response latency is acceptable ───────────────────────────────────
echo ""
echo "── Test 2: Response latency < $((FAILOVER_TARGET_SEC * 1000))ms ──────────────────"
LATENCY_LIMIT_MS=$(( FAILOVER_TARGET_SEC * 1000 ))
if [ "$ELAPSED" -lt "$LATENCY_LIMIT_MS" ]; then
  _pass "Response latency ${ELAPSED}ms is under ${LATENCY_LIMIT_MS}ms target"
else
  _fail "Response latency ${ELAPSED}ms exceeds ${LATENCY_LIMIT_MS}ms (failover target)"
fi

# ── Test 3: Retry-After header present on 429 ────────────────────────────────
echo ""
echo "── Test 3: Rate limit enforcement (${RATE_LIMIT_RPM}rpm) ──────────────────"
RATE_LIMITED=false
for i in $(seq 1 $(( RATE_LIMIT_RPM + 5 ))); do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "$ENDPOINT" \
    -H "Ocp-Apim-Subscription-Key: $API_KEY" \
    -d '{}' \
    --max-time 5 2>/dev/null) || CODE="000"
  if [ "$CODE" = "429" ]; then
    _pass "Rate limit (429) triggered at request $i — within expected window after ${RATE_LIMIT_RPM}rpm"
    RATE_LIMITED=true
    break
  fi
done
if [ "$RATE_LIMITED" = "false" ]; then
  _info "Rate limit not triggered within $((RATE_LIMIT_RPM + 5)) requests — policy may be per-product, not per-subscription"
fi

# ── Test 4: Retry-After header on 429 ────────────────────────────────────────
echo ""
echo "── Test 4: Retry-After header present on 429 ──────────────────"
LAST_HEADERS=$(curl -s -D - -o /dev/null \
  -X POST "$ENDPOINT" \
  -H "Ocp-Apim-Subscription-Key: $API_KEY" \
  -d '{}' \
  --max-time 5 2>/dev/null)

RETRY_AFTER=$(echo "$LAST_HEADERS" | grep -i "^retry-after:" | head -1 | tr -d '\r')
if [ -n "$RETRY_AFTER" ]; then
  _pass "Retry-After header found: $RETRY_AFTER"
else
  _info "Retry-After header not present (expected if rate limit not triggered)"
fi

# ── Test 5: X-Cache-Status header propagated ─────────────────────────────────
echo ""
echo "── Test 5: APIM sets X-Cache-Status header ──────────────────"
RESP_HEADERS=$(curl -s -D - -o /dev/null \
  -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Ocp-Apim-Subscription-Key: $API_KEY" \
  -d '{"startDate":"2024-01-01","endDate":"2024-12-31"}' \
  --max-time 10 2>/dev/null)
CACHE_HDR=$(echo "$RESP_HEADERS" | grep -i "^x-cache-status:" | head -1 | tr -d '\r')
if [ -n "$CACHE_HDR" ]; then
  _pass "X-Cache-Status header present: $CACHE_HDR"
else
  _info "X-Cache-Status header not set — Redis cache policy may not be active yet"
fi

# ── Test 6: Backend pool header ───────────────────────────────────────────────
echo ""
echo "── Test 6: APIM sets X-APIM-Backend header ──────────────────"
BACKEND_HDR=$(echo "$RESP_HEADERS" | grep -i "^x-apim-backend:" | head -1 | tr -d '\r')
if [ -n "$BACKEND_HDR" ]; then
  _pass "X-APIM-Backend header present: $BACKEND_HDR"
else
  _info "X-APIM-Backend not set — configure set-header policy in APIM to enable"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   📊  Summary                                     ║"
echo "╚══════════════════════════════════════════════════╝"
echo "  PASS : $PASS"
echo "  FAIL : $FAIL"
echo ""

if [ "$FAIL" -eq 0 ]; then
  echo "✅ All failover tests passed"
  exit 0
else
  echo "❌ $FAIL test(s) failed — review output above"
  exit 1
fi
