# validate-cache-hit-rate.ps1
# Validates that APIM Redis cache achieves >20% hit rate for /fetchChartData
#
# Usage:
#   $env:APIM_SUBSCRIPTION_KEY = "<your-key>"
#   .\validate-cache-hit-rate.ps1 [-ApimUrl "https://..."] [-ApiKey "..."] [-Requests 10] [-HitTargetPct 20]

param(
    [string]$ApimUrl      = ($env:APIM_URL ?? "https://apim-callcenter100.azure-api.net"),
    [string]$ApiKey       = ($env:APIM_SUBSCRIPTION_KEY ?? ""),
    [int]   $Requests     = 10,
    [int]   $HitTargetPct = 20
)

$ErrorActionPreference = "Stop"

# Same payload on every call — APIM should cache after first MISS
$Payload = '{"startDate":"2024-01-01","endDate":"2024-12-31"}'
$Endpoint = "$ApimUrl/callcenter/api/fetchChartData"

$Hits     = 0
$Passes   = 0
$Failures = 0

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════╗"
Write-Host "║   🧪  Cache Hit Rate Validation — Phase 3        ║"
Write-Host "╚══════════════════════════════════════════════════╝"
Write-Host "  APIM URL : $ApimUrl"
Write-Host "  Requests : $Requests"
Write-Host "  Target   : >$($HitTargetPct)% cache-hit rate"
Write-Host ""

if ([string]::IsNullOrWhiteSpace($ApiKey)) {
    Write-Warning "APIM_SUBSCRIPTION_KEY is not set. Requests may receive 401."
}

for ($i = 1; $i -le $Requests; $i++) {
    $HttpCode    = "000"
    $CacheStatus = "UNKNOWN"

    try {
        $Headers = @{
            "Content-Type"                = "application/json"
            "Ocp-Apim-Subscription-Key"   = $ApiKey
        }

        $Response = Invoke-WebRequest `
            -Uri     $Endpoint `
            -Method  Post `
            -Headers $Headers `
            -Body    $Payload `
            -TimeoutSec 15 `
            -ErrorAction Stop

        $HttpCode = $Response.StatusCode

        if ($Response.Headers["X-Cache-Status"]) {
            $CacheStatus = $Response.Headers["X-Cache-Status"].ToString().ToUpper()
        }

        $Passes++
        if ($CacheStatus -eq "HIT") { $Hits++ }
    }
    catch [System.Net.WebException] {
        $HttpCode = [int]$_.Exception.Response.StatusCode
        $Failures++
    }
    catch {
        $Failures++
    }

    Write-Host ("  Request {0,2}: HTTP {1,-3} | Cache: {2}" -f $i, $HttpCode, $CacheStatus)
    Start-Sleep -Milliseconds 100
}

# Calculate hit rate only among successful responses
$HitRate = if ($Passes -gt 0) { [math]::Floor($Hits * 100 / $Passes) } else { 0 }

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════╗"
Write-Host "║   📊  Results                                     ║"
Write-Host "╚══════════════════════════════════════════════════╝"
Write-Host ("  Successful requests : {0} / {1}" -f $Passes, $Requests)
Write-Host ("  Failed requests     : {0}" -f $Failures)
Write-Host ("  Cache HITs          : {0} / {1} (of successful)" -f $Hits, $Passes)
Write-Host ("  Hit Rate            : {0}%" -f $HitRate)
Write-Host ("  Target              : >{0}%" -f $HitTargetPct)
Write-Host ""

if ($Passes -eq 0) {
    Write-Host "❌ FAIL: No successful responses. Check APIM_SUBSCRIPTION_KEY and connectivity."
    exit 2
}
elseif ($HitRate -gt $HitTargetPct) {
    Write-Host "✅ PASS: Cache hit rate $($HitRate)% exceeds $($HitTargetPct)% target"
    exit 0
}
else {
    Write-Host "❌ FAIL: Cache hit rate $($HitRate)% is below $($HitTargetPct)% target"
    Write-Host "   → Verify Redis cache-lookup policy is deployed in APIM"
    Write-Host "   → Ensure identical payloads trigger cache lookup"
    exit 1
}
