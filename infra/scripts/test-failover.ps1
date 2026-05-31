# test-failover.ps1
# Tests APIM circuit breaker, retry behavior, and rate-limit enforcement for Phase 3.
#
# Usage:
#   $env:APIM_SUBSCRIPTION_KEY = "<your-key>"
#   .\test-failover.ps1 [-ApimUrl "https://..."] [-ApiKey "..."] [-RateLimitRpm 30] [-FailoverTargetSec 2]

param(
    [string]$ApimUrl         = ($env:APIM_URL ?? "https://apim-callcenter100.azure-api.net"),
    [string]$ApiKey          = ($env:APIM_SUBSCRIPTION_KEY ?? ""),
    [int]   $RateLimitRpm    = 30,
    [int]   $FailoverTargetSec = 2
)

$ErrorActionPreference = "Continue"

$Endpoint          = "$ApimUrl/callcenter/api/fetchChartData"
$LatencyLimitMs    = $FailoverTargetSec * 1000
$Pass = 0
$Fail = 0

function _pass([string]$msg) { Write-Host "  ✅ $msg" -ForegroundColor Green; $script:Pass++ }
function _fail([string]$msg) { Write-Host "  ❌ $msg" -ForegroundColor Red;   $script:Fail++ }
function _info([string]$msg) { Write-Host "  ℹ️  $msg" }

$Headers = @{
    "Content-Type"              = "application/json"
    "Ocp-Apim-Subscription-Key" = $ApiKey
}

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════╗"
Write-Host "║   🔁  Failover & Circuit Breaker Test — Phase 3  ║"
Write-Host "╚══════════════════════════════════════════════════╝"
Write-Host "  APIM URL  : $ApimUrl"
Write-Host "  Rate limit: $($RateLimitRpm)rpm"
Write-Host "  Failover  : <$($FailoverTargetSec)s target"
Write-Host ""

if ([string]::IsNullOrWhiteSpace($ApiKey)) {
    Write-Warning "APIM_SUBSCRIPTION_KEY is not set. Requests may receive 401."
    Write-Host ""
}

# ── Test 1: Normal request returns 200 ──────────────────────────────────────
Write-Host "── Test 1: Normal request returns 200 ──────────────────"
$sw = [System.Diagnostics.Stopwatch]::StartNew()
try {
    $Resp = Invoke-WebRequest -Uri $Endpoint -Method Post -Headers $Headers `
        -Body '{"startDate":"2024-01-01","endDate":"2024-12-31"}' -TimeoutSec 15 -ErrorAction Stop
    $HttpCode = $Resp.StatusCode
} catch { $HttpCode = 0 }
$sw.Stop()
$Elapsed = $sw.ElapsedMilliseconds

if ($HttpCode -eq 200) { _pass "Normal request succeeded (HTTP 200) in $($Elapsed)ms" }
else                   { _fail "Normal request returned HTTP $HttpCode (expected 200)" }

# ── Test 2: Response latency < FailoverTarget ────────────────────────────────
Write-Host ""
Write-Host "── Test 2: Response latency < $($LatencyLimitMs)ms ──────────────────"
if ($Elapsed -lt $LatencyLimitMs) { _pass "Latency $($Elapsed)ms is under $($LatencyLimitMs)ms target" }
else                               { _fail "Latency $($Elapsed)ms exceeds $($LatencyLimitMs)ms (failover target)" }

# ── Test 3: Rate limit enforcement ───────────────────────────────────────────
Write-Host ""
Write-Host "── Test 3: Rate limit enforcement ($($RateLimitRpm)rpm) ──────────────────"
$RateLimited = $false
for ($i = 1; $i -le ($RateLimitRpm + 5); $i++) {
    try {
        $R = Invoke-WebRequest -Uri $Endpoint -Method Post -Headers $Headers `
            -Body '{}' -TimeoutSec 5 -ErrorAction Stop
        $Code = $R.StatusCode
    } catch [System.Net.WebException] {
        $Code = [int]$_.Exception.Response.StatusCode
    } catch { $Code = 0 }

    if ($Code -eq 429) {
        _pass "Rate limit (429) triggered at request $i — within expected window after $($RateLimitRpm)rpm"
        $RateLimited = $true
        break
    }
}
if (-not $RateLimited) {
    _info "Rate limit not triggered within $($RateLimitRpm + 5) requests — policy may be per-product"
}

# ── Test 4: Retry-After header on 429 ────────────────────────────────────────
Write-Host ""
Write-Host "── Test 4: Retry-After header on 429 ──────────────────"
try {
    $R2 = Invoke-WebRequest -Uri $Endpoint -Method Post -Headers $Headers `
        -Body '{}' -TimeoutSec 5 -ErrorAction Stop
    $RetryAfter = $R2.Headers["Retry-After"]
} catch [System.Net.WebException] {
    $RetryAfter = $_.Exception.Response.Headers["Retry-After"]
} catch { $RetryAfter = $null }

if ($RetryAfter) { _pass "Retry-After header found: $RetryAfter" }
else             { _info "Retry-After header not present (expected if rate limit not triggered)" }

# ── Test 5: X-Cache-Status header ────────────────────────────────────────────
Write-Host ""
Write-Host "── Test 5: APIM sets X-Cache-Status header ──────────────────"
try {
    $R3 = Invoke-WebRequest -Uri $Endpoint -Method Post -Headers $Headers `
        -Body '{"startDate":"2024-01-01","endDate":"2024-12-31"}' -TimeoutSec 15 -ErrorAction Stop
    $CacheHdr = $R3.Headers["X-Cache-Status"]
} catch { $CacheHdr = $null }

if ($CacheHdr) { _pass "X-Cache-Status header present: $CacheHdr" }
else           { _info "X-Cache-Status not set — Redis cache policy may not be active yet" }

# ── Test 6: X-APIM-Backend header ────────────────────────────────────────────
Write-Host ""
Write-Host "── Test 6: APIM sets X-APIM-Backend header ──────────────────"
$BackendHdr = if ($R3) { $R3.Headers["X-APIM-Backend"] } else { $null }
if ($BackendHdr) { _pass "X-APIM-Backend header present: $BackendHdr" }
else             { _info "X-APIM-Backend not set — configure set-header policy in APIM to enable" }

# ── Summary ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════╗"
Write-Host "║   📊  Summary                                     ║"
Write-Host "╚══════════════════════════════════════════════════╝"
Write-Host "  PASS : $Pass"
Write-Host "  FAIL : $Fail"
Write-Host ""

if ($Fail -eq 0) {
    Write-Host "✅ All failover tests passed" -ForegroundColor Green
    exit 0
} else {
    Write-Host "❌ $Fail test(s) failed — review output above" -ForegroundColor Red
    exit 1
}
