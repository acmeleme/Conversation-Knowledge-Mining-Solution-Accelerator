#!/bin/bash
# validate-cache-hit-rate.sh
# Validates that APIM Redis cache achieves >20% hit rate for /fetchChartData
#
# Usage:
#   export APIM_SUBSCRIPTION_KEY="<your-key>"
#   export APIM_URL="https://apim-callcenter100.azure-api.net"   # optional override
#   bash validate-cache-hit-rate.sh

set -euo pipefail

APIM_URL="${APIM_URL:-https://apim-callcenter100.azure-api.net}"
API_KEY="${APIM_SUBSCRIPTION_KEY:-}"
REQUESTS="${REQUESTS:-10}"
HIT_TARGET="${HIT_TARGET_PCT:-20}"
HITS=0
PASSES=0
FAILURES=0

HEADER_DIR="$(mktemp -d)"
trap 'rm -rf "$HEADER_DIR"' EXIT

# Same payload on every request — APIM should cache after the first MISS
PAYLOAD='{"startDate":"2024-01-01","endDate":"2024-12-31"}'

echo "╔══════════════════════════════════════════════════╗"
echo "║   🧪  Cache Hit Rate Validation — Phase 3        ║"
echo "╚══════════════════════════════════════════════════╝"
echo "  APIM URL : $APIM_URL"
echo "  Requests : $REQUESTS"
echo "  Target   : >${HIT_TARGET}% cache-hit rate"
echo ""

if [ -z "$API_KEY" ]; then
  echo "⚠️  WARNING: APIM_SUBSCRIPTION_KEY is not set. Requests may receive 401."
fi

for i in $(seq 1 "$REQUESTS"); do
  HEADER_FILE="$HEADER_DIR/headers-$i.txt"

  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "$APIM_URL/callcenter/api/fetchChartData" \
    -H "Content-Type: application/json" \
    -H "Ocp-Apim-Subscription-Key: $API_KEY" \
    -D "$HEADER_FILE" \
    -d "$PAYLOAD" \
    --max-time 15 \
    2>/dev/null) || HTTP_CODE="000"

  CACHE_STATUS=$(grep -i "^x-cache-status:" "$HEADER_FILE" 2>/dev/null \
    | awk '{print $2}' | tr -d '\r\n' | tr '[:lower:]' '[:upper:]') || CACHE_STATUS="UNKNOWN"

  printf "  Request %2d: HTTP %-3s | Cache: %s\n" "$i" "$HTTP_CODE" "${CACHE_STATUS:-UNKNOWN}"

  if [ "$HTTP_CODE" = "200" ]; then
    PASSES=$((PASSES + 1))
    if [ "$CACHE_STATUS" = "HIT" ]; then
      HITS=$((HITS + 1))
    fi
  else
    FAILURES=$((FAILURES + 1))
  fi

  sleep 0.1
done

# Calculate hit rate only among successful (200) responses
if [ "$PASSES" -gt 0 ]; then
  HIT_RATE=$(echo "scale=0; $HITS * 100 / $PASSES" | bc)
else
  HIT_RATE=0
fi

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   📊  Results                                     ║"
echo "╚══════════════════════════════════════════════════╝"
printf "  Successful requests : %d / %d\n" "$PASSES" "$REQUESTS"
printf "  Failed requests     : %d\n" "$FAILURES"
printf "  Cache HITs          : %d / %d (of successful)\n" "$HITS" "$PASSES"
printf "  Hit Rate            : %d%%\n" "$HIT_RATE"
printf "  Target              : >%d%%\n" "$HIT_TARGET"
echo ""

if [ "$PASSES" -eq 0 ]; then
  echo "❌ FAIL: No successful responses. Check APIM_SUBSCRIPTION_KEY and connectivity."
  exit 2
elif [ "$HIT_RATE" -gt "$HIT_TARGET" ]; then
  echo "✅ PASS: Cache hit rate ${HIT_RATE}% exceeds ${HIT_TARGET}% target"
  exit 0
else
  echo "❌ FAIL: Cache hit rate ${HIT_RATE}% is below ${HIT_TARGET}% target"
  echo "   → Verify Redis cache-lookup policy is deployed in APIM"
  echo "   → Ensure identical payloads trigger cache lookup"
  exit 1
fi
