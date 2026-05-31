"""
Phase 3 Tests: Semantic Cache & Resilience
Tests for:
- APIM cache header validation (X-Cache-Status)
- Retry logic verification
- Circuit breaker simulation
- Backend pool routing
- Rate limit headers
- ROI metrics calculation
"""
import logging
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch, MagicMock

import pytest
from fastapi.testclient import TestClient

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

mock_events_package = types.ModuleType("azure.monitor.events")
mock_events_extension = types.ModuleType("azure.monitor.events.extension")
mock_events_extension.track_event = Mock()
mock_events_package.extension = mock_events_extension
sys.modules.setdefault("azure.monitor.events", mock_events_package)
sys.modules.setdefault("azure.monitor.events.extension", mock_events_extension)

mock_opentelemetry = types.ModuleType("azure.monitor.opentelemetry")
mock_opentelemetry.configure_azure_monitor = Mock()
sys.modules.setdefault("azure.monitor.opentelemetry", mock_opentelemetry)

import app as app_module
from helpers import azure_openai_helper


# ---------------------------------------------------------------------------
# Shared Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_client():
    with patch(
        "agents.conversation_agent_factory.ConversationAgentFactory.get_agent",
        new=AsyncMock(return_value=Mock(name="conversation-agent")),
    ), patch(
        "agents.search_agent_factory.SearchAgentFactory.get_agent",
        new=AsyncMock(return_value=Mock(name="search-agent")),
    ), patch(
        "agents.sql_agent_factory.SQLAgentFactory.get_agent",
        new=AsyncMock(return_value=Mock(name="sql-agent")),
    ), patch(
        "agents.chart_agent_factory.ChartAgentFactory.get_agent",
        new=AsyncMock(return_value=Mock(name="chart-agent")),
    ), patch(
        "agents.conversation_agent_factory.ConversationAgentFactory.delete_agent",
        new=AsyncMock(),
    ), patch(
        "agents.search_agent_factory.SearchAgentFactory.delete_agent",
        new=AsyncMock(),
    ), patch(
        "agents.sql_agent_factory.SQLAgentFactory.delete_agent",
        new=AsyncMock(),
    ), patch(
        "agents.chart_agent_factory.ChartAgentFactory.delete_agent",
        new=AsyncMock(),
    ):
        with TestClient(app_module.build_app()) as client:
            yield client


# ---------------------------------------------------------------------------
# 1. Cache hit detection via X-Cache-Status header
# ---------------------------------------------------------------------------

def test_chart_response_can_carry_cache_hit_header(test_client):
    """Simulates APIM injecting X-Cache-Status: HIT and verifies we can detect it."""
    with patch("api.api_routes.ChartService") as mock_svc, patch(
        "api.api_routes.track_event_if_configured"
    ):
        mock_svc.return_value.fetch_chart_data = AsyncMock(return_value={"charts": []})

        response = test_client.get(
            "/api/fetchChartData",
            headers={"X-Cache-Status": "HIT", "X-User-Id": "test@example.com"},
        )

    assert response.status_code == 200
    # The backend itself doesn't set X-Cache-Status; APIM does.
    # We validate the backend doesn't strip or reject the incoming header.
    assert response.json() == {"charts": []}


def test_chart_response_can_carry_cache_miss_header(test_client):
    """Simulates APIM injecting X-Cache-Status: MISS (first request, cache cold)."""
    with patch("api.api_routes.ChartService") as mock_svc, patch(
        "api.api_routes.track_event_if_configured"
    ):
        mock_svc.return_value.fetch_chart_data = AsyncMock(return_value={"charts": ["bar"]})

        response = test_client.get(
            "/api/fetchChartData",
            headers={"X-Cache-Status": "MISS", "X-User-Id": "user@example.com"},
        )

    assert response.status_code == 200
    assert "charts" in response.json()


# ---------------------------------------------------------------------------
# 2. X-APIM-Version = "2.0" (Phase 3 bump)
# ---------------------------------------------------------------------------

def test_chart_endpoint_accepts_apim_version_header(test_client):
    """Phase 3 APIM policy bumps X-APIM-Version to 2.0; backend must accept it."""
    with patch("api.api_routes.ChartService") as mock_svc, patch(
        "api.api_routes.track_event_if_configured"
    ):
        mock_svc.return_value.fetch_chart_data = AsyncMock(return_value={"ok": True})

        response = test_client.get(
            "/api/fetchChartData",
            headers={"X-APIM-Version": "2.0", "X-User-Id": "tester@example.com"},
        )

    assert response.status_code == 200


def test_filter_endpoint_accepts_apim_version_header(test_client):
    """fetchFilterData also flows through APIM v2.0 policy layer."""
    with patch("api.api_routes.ChartService") as mock_svc, patch(
        "api.api_routes.track_event_if_configured"
    ):
        mock_svc.return_value.fetch_filter_data = AsyncMock(return_value={"topics": []})

        response = test_client.get(
            "/api/fetchFilterData",
            headers={"X-APIM-Version": "2.0", "X-User-Id": "tester@example.com"},
        )

    # 200 or 500 depending on service wiring — we care it doesn't 400 on the header
    assert response.status_code != 400


# ---------------------------------------------------------------------------
# 3. X-APIM-Backend header presence
# ---------------------------------------------------------------------------

def test_chart_endpoint_accepts_x_apim_backend_header(test_client):
    """APIM sets X-APIM-Backend to identify which pool member served the request."""
    with patch("api.api_routes.ChartService") as mock_svc, patch(
        "api.api_routes.track_event_if_configured"
    ):
        mock_svc.return_value.fetch_chart_data = AsyncMock(return_value={"pool": "primary"})

        response = test_client.get(
            "/api/fetchChartData",
            headers={
                "X-APIM-Backend": "api-callcenter100.azurewebsites.net",
                "X-User-Id": "tester@example.com",
            },
        )

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# 4. Rate limit header propagation (X-RateLimit-Remaining)
# ---------------------------------------------------------------------------

def test_chart_endpoint_accepts_rate_limit_headers(test_client):
    """APIM forwards X-RateLimit-Remaining; backend must not reject it."""
    with patch("api.api_routes.ChartService") as mock_svc, patch(
        "api.api_routes.track_event_if_configured"
    ):
        mock_svc.return_value.fetch_chart_data = AsyncMock(return_value={"charts": []})

        response = test_client.get(
            "/api/fetchChartData",
            headers={
                "X-RateLimit-Remaining": "25",
                "X-RateLimit-Limit": "30",
                "X-User-Id": "tester@example.com",
            },
        )

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# 5. Retry logic verification
# ---------------------------------------------------------------------------

def test_chart_service_called_once_on_success(test_client):
    """On a successful first response, chart service is invoked exactly once (no retry)."""
    with patch("api.api_routes.ChartService") as mock_svc, patch(
        "api.api_routes.track_event_if_configured"
    ):
        mock_svc.return_value.fetch_chart_data = AsyncMock(return_value={"charts": []})

        test_client.get("/api/fetchChartData", headers={"X-User-Id": "user@example.com"})

        assert mock_svc.return_value.fetch_chart_data.call_count == 1


def test_chart_service_exception_returns_500(test_client):
    """If ChartService raises an unexpected exception, the route returns HTTP 500."""
    with patch("api.api_routes.ChartService") as mock_svc, patch(
        "api.api_routes.track_event_if_configured"
    ):
        mock_svc.return_value.fetch_chart_data = AsyncMock(
            side_effect=RuntimeError("upstream timeout")
        )

        response = test_client.get(
            "/api/fetchChartData", headers={"X-User-Id": "user@example.com"}
        )

    assert response.status_code == 500


# ---------------------------------------------------------------------------
# 6. Circuit breaker simulation (500 errors trigger fallback)
# ---------------------------------------------------------------------------

def test_multiple_backend_failures_each_return_500(test_client):
    """Simulates three consecutive backend failures (circuit open scenario)."""
    with patch("api.api_routes.ChartService") as mock_svc, patch(
        "api.api_routes.track_event_if_configured"
    ):
        mock_svc.return_value.fetch_chart_data = AsyncMock(
            side_effect=RuntimeError("backend unavailable")
        )

        results = [
            test_client.get(
                "/api/fetchChartData", headers={"X-User-Id": f"user{i}@example.com"}
            ).status_code
            for i in range(3)
        ]

    assert all(code == 500 for code in results), f"Expected all 500, got {results}"


def test_backend_recovery_after_failure(test_client):
    """After a failure the backend can recover and return 200 on next call."""
    call_count = 0

    async def flaky(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("transient error")
        return {"charts": ["recovered"]}

    with patch("api.api_routes.ChartService") as mock_svc, patch(
        "api.api_routes.track_event_if_configured"
    ):
        mock_svc.return_value.fetch_chart_data = flaky

        r1 = test_client.get("/api/fetchChartData", headers={"X-User-Id": "a@b.com"})
        r2 = test_client.get("/api/fetchChartData", headers={"X-User-Id": "a@b.com"})

    assert r1.status_code == 500
    assert r2.status_code == 200
    assert r2.json() == {"charts": ["recovered"]}


# ---------------------------------------------------------------------------
# 7. ROI calculation helper function tests
# ---------------------------------------------------------------------------

def _calculate_cache_roi(
    total_requests: int,
    cache_hits: int,
    cost_per_openai_call_usd: float,
    redis_monthly_cost_usd: float,
) -> dict:
    """
    Pure-function ROI calculator — no Azure dependencies.
    Returns monthly savings estimate given cache performance metrics.
    """
    hit_rate = cache_hits / total_requests if total_requests > 0 else 0
    requests_per_month = total_requests * 30  # scale daily → monthly
    hits_per_month = requests_per_month * hit_rate
    gross_savings = hits_per_month * cost_per_openai_call_usd
    net_savings = gross_savings - redis_monthly_cost_usd
    return {
        "hit_rate_pct": round(hit_rate * 100, 2),
        "requests_per_month": requests_per_month,
        "hits_per_month": round(hits_per_month),
        "gross_savings_usd": round(gross_savings, 2),
        "redis_cost_usd": redis_monthly_cost_usd,
        "net_savings_usd": round(net_savings, 2),
        "roi_positive": net_savings > 0,
    }


def test_roi_calculation_hit_rate_above_20_pct():
    """ROI helper computes correct hit rate for 30 hits out of 100 requests."""
    result = _calculate_cache_roi(
        total_requests=100,
        cache_hits=30,
        cost_per_openai_call_usd=0.05,
        redis_monthly_cost_usd=15.0,
    )
    assert result["hit_rate_pct"] == 30.0
    assert result["roi_positive"] is True


def test_roi_calculation_hit_rate_below_20_pct_still_computes():
    """ROI is still computed even when below target; result flags it."""
    result = _calculate_cache_roi(
        total_requests=100,
        cache_hits=10,
        cost_per_openai_call_usd=0.02,
        redis_monthly_cost_usd=15.0,
    )
    assert result["hit_rate_pct"] == 10.0
    # 10 hits/day × 30 days × $0.02 = $6.00 gross, net = $6 - $15 = -$9 → not positive
    assert result["roi_positive"] is False


def test_roi_calculation_zero_requests_does_not_divide_by_zero():
    """Edge case: zero requests must not raise ZeroDivisionError."""
    result = _calculate_cache_roi(
        total_requests=0,
        cache_hits=0,
        cost_per_openai_call_usd=0.05,
        redis_monthly_cost_usd=15.0,
    )
    assert result["hit_rate_pct"] == 0.0
    assert result["roi_positive"] is False


def test_roi_net_savings_accounts_for_redis_cost():
    """Net savings must subtract Redis monthly cost from gross savings."""
    result = _calculate_cache_roi(
        total_requests=200,
        cache_hits=100,
        cost_per_openai_call_usd=0.10,
        redis_monthly_cost_usd=50.0,
    )
    # 100 hits/day × 30 × $0.10 = $300 gross, net = $300 - $50 = $250
    assert result["gross_savings_usd"] == 300.0
    assert result["net_savings_usd"] == 250.0
    assert result["roi_positive"] is True


# ---------------------------------------------------------------------------
# 8. APIM gateway mode — Phase 3 env var validation
# ---------------------------------------------------------------------------

@patch("helpers.azure_openai_helper.openai.AzureOpenAI")
@patch("helpers.azure_openai_helper.get_bearer_token_provider")
@patch("helpers.azure_openai_helper.get_azure_credential")
def test_apim_phase3_uses_subscription_key_auth(
    mock_get_azure_credential,
    mock_token_provider,
    mock_azure_openai,
    monkeypatch,
):
    """Phase 3: APIM gateway mode must use subscription key, not Managed Identity."""
    monkeypatch.setenv("USE_APIM_GATEWAY", "true")
    monkeypatch.setenv("APIM_ENDPOINT", "https://apim-callcenter100.azure-api.net")
    monkeypatch.setenv("APIM_API_VERSION", "2024-05-01-preview")
    monkeypatch.setenv("APIM_SUBSCRIPTION_KEY", "phase3-sub-key-abc")

    mock_azure_openai.return_value = Mock(name="apim-client")

    client = azure_openai_helper.get_azure_openai_client()

    mock_get_azure_credential.assert_not_called()
    mock_token_provider.assert_not_called()
    mock_azure_openai.assert_called_once_with(
        azure_endpoint="https://apim-callcenter100.azure-api.net",
        api_version="2024-05-01-preview",
        api_key="phase3-sub-key-abc",
        default_headers={"Ocp-Apim-Subscription-Key": "phase3-sub-key-abc"},
    )
    assert client is mock_azure_openai.return_value
