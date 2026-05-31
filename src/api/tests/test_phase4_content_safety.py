"""
test_phase4_content_safety.py — Phase 4: Content Safety & Compliance Tests

Tests for:
- Content Safety response parsing and threshold enforcement
- Audit log header presence and format
- APIM policy behavior simulation
- Compliance evidence (LGPD/ISO 27001 required fields)
- Key Vault integration patterns
- Error handling and safe-fail behavior
"""

import sys
import types
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
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
from helpers.content_safety_helper import (
    CONTENT_SAFETY_BLOCK_THRESHOLD,
    CONTENT_SAFETY_CATEGORIES,
    build_audit_log_entry,
    build_content_safety_payload,
    evaluate_content_safety_response,
    extract_user_message,
    resolve_apim_subscription_key,
)


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


class TestBuildContentSafetyPayload:
    def test_safe_text_payload_structure(self):
        """Content Safety payload must include text, categories, outputType."""
        payload = build_content_safety_payload("Hello world")

        assert payload["text"] == "Hello world"
        assert payload["categories"] == CONTENT_SAFETY_CATEGORIES
        assert payload["outputType"] == "FourSeverityLevels"

    def test_all_four_categories_present(self):
        """All 4 categories must be present: Hate, Violence, Sexual, SelfHarm."""
        payload = build_content_safety_payload("test")

        assert set(payload["categories"]) == {"Hate", "Violence", "Sexual", "SelfHarm"}

    def test_text_truncated_at_5000_chars(self):
        """Text longer than 5000 chars must be truncated."""
        payload = build_content_safety_payload("x" * 6000)

        assert len(payload["text"]) == 5000

    def test_empty_text_replaced_with_placeholder(self):
        """Empty text should be replaced with 'empty' placeholder."""
        payload = build_content_safety_payload("")

        assert payload["text"] == "empty"


class TestEvaluateContentSafetyResponse:
    @staticmethod
    def _make_response(categories):
        return {
            "categoriesAnalysis": [
                {"category": category, "severity": severity}
                for category, severity in categories
            ]
        }

    def test_safe_content_returns_safe(self):
        response = self._make_response(
            [("Hate", 0), ("Violence", 1), ("Sexual", 3), ("SelfHarm", 2)]
        )

        assert evaluate_content_safety_response(response) == "SAFE"

    def test_blocked_hate_content_returns_category(self):
        response = self._make_response(
            [("Hate", 4), ("Violence", 0), ("Sexual", 0), ("SelfHarm", 0)]
        )

        assert evaluate_content_safety_response(response) == "BLOCKED:Hate"

    def test_blocked_violence_content_returns_category(self):
        response = self._make_response(
            [("Hate", 0), ("Violence", 5), ("Sexual", 0), ("SelfHarm", 0)]
        )

        assert evaluate_content_safety_response(response) == "BLOCKED:Violence"

    def test_blocked_sexual_content_returns_category(self):
        response = self._make_response(
            [("Hate", 0), ("Violence", 0), ("Sexual", 4), ("SelfHarm", 0)]
        )

        assert evaluate_content_safety_response(response) == "BLOCKED:Sexual"

    def test_blocked_self_harm_content_returns_category(self):
        response = self._make_response(
            [("Hate", 0), ("Violence", 0), ("Sexual", 0), ("SelfHarm", 4)]
        )

        assert evaluate_content_safety_response(response) == "BLOCKED:SelfHarm"

    def test_severity_3_is_allowed(self):
        response = self._make_response(
            [("Hate", 3), ("Violence", 0), ("Sexual", 0), ("SelfHarm", 0)]
        )

        assert evaluate_content_safety_response(response) == "SAFE"

    def test_severity_4_is_blocked(self):
        response = self._make_response(
            [("Hate", 4), ("Violence", 0), ("Sexual", 0), ("SelfHarm", 0)]
        )

        assert evaluate_content_safety_response(response) == "BLOCKED:Hate"

    def test_unavailable_when_response_missing(self):
        assert evaluate_content_safety_response(None) == "UNAVAILABLE"
        assert evaluate_content_safety_response({}) == "UNAVAILABLE"

    def test_safe_when_no_categories_analysis(self):
        assert evaluate_content_safety_response({"categoriesAnalysis": []}) == "SAFE"

    def test_unavailable_when_categories_are_malformed(self):
        assert evaluate_content_safety_response({"categoriesAnalysis": "bad"}) == "UNAVAILABLE"


class TestExtractUserMessage:
    def test_extracts_last_user_message(self):
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "First"},
            {"role": "assistant", "content": "Answer"},
            {"role": "user", "content": "Second"},
        ]

        assert extract_user_message(messages) == "Second"

    def test_empty_messages_returns_empty(self):
        assert extract_user_message([]) == ""

    def test_non_string_content_returns_empty(self):
        assert extract_user_message([{"role": "user", "content": ["bad"]}]) == ""


class TestBuildAuditLogEntry:
    def test_audit_log_has_required_lgpd_fields(self):
        entry = build_audit_log_entry(
            user_id="user@test.com",
            request_id="req-123",
            content_safety_result="SAFE",
            endpoint="/api/chat",
        )

        assert set(entry) >= {
            "user_id",
            "request_id",
            "content_safety_result",
            "endpoint",
            "timestamp",
            "phase",
        }

    def test_timestamp_is_iso8601(self):
        entry = build_audit_log_entry("u", "r", "SAFE", "/test")
        parsed = datetime.fromisoformat(entry["timestamp"])

        assert parsed.tzinfo is not None

    def test_anonymous_user_when_user_missing(self):
        entry = build_audit_log_entry(None, "req-456", "SAFE", "/api/chat")

        assert entry["user_id"] == "anonymous"

    def test_block_threshold_is_4(self):
        assert CONTENT_SAFETY_BLOCK_THRESHOLD == 4


class TestResolveApimSubscriptionKey:
    def test_env_value_takes_precedence_over_key_vault(self):
        key_vault_client = Mock()
        key_vault_client.get_secret.return_value.value = "from-key-vault"

        key = resolve_apim_subscription_key(
            env={"APIM_SUBSCRIPTION_KEY": "from-env"},
            key_vault_client=key_vault_client,
        )

        assert key == "from-env"
        key_vault_client.get_secret.assert_not_called()

    def test_falls_back_gracefully_when_key_vault_unavailable(self):
        key_vault_client = Mock()
        key_vault_client.get_secret.side_effect = RuntimeError("vault offline")

        assert resolve_apim_subscription_key(env={}, key_vault_client=key_vault_client) is None


class TestPhase4EndpointBehavior:
    def test_safe_content_header_allows_request(self, test_client):
        with patch("api.api_routes.ChartService") as mock_service, patch(
            "api.api_routes.track_event_if_configured"
        ):
            mock_service.return_value.fetch_chart_data = AsyncMock(return_value={"ok": True})

            response = test_client.get(
                "/api/fetchChartData",
                headers={
                    "X-Content-Safety-Result": "SAFE",
                    "X-MS-CLIENT-PRINCIPAL-NAME": "safe.user@example.com",
                },
            )

        assert response.status_code == 200
        assert response.json() == {"ok": True}
        assert response.headers["X-Content-Safety-Result"] == "SAFE"

    def test_unavailable_content_safety_allows_request(self, test_client):
        with patch("api.api_routes.ChartService") as mock_service, patch(
            "api.api_routes.track_event_if_configured"
        ):
            mock_service.return_value.fetch_chart_data = AsyncMock(return_value={"ok": True})

            response = test_client.get(
                "/api/fetchChartData",
                headers={"X-Content-Safety-Result": "UNAVAILABLE"},
            )

        assert response.status_code == 200
        assert response.headers["X-Content-Safety-Result"] == "UNAVAILABLE"

    def test_audit_headers_present_on_successful_response(self, test_client):
        with patch("api.api_routes.ChartService") as mock_service, patch(
            "api.api_routes.track_event_if_configured"
        ):
            mock_service.return_value.fetch_chart_data = AsyncMock(return_value={"ok": True})

            response = test_client.get(
                "/api/fetchChartData",
                headers={"X-MS-CLIENT-PRINCIPAL-NAME": "audit.user@example.com"},
            )

        assert response.status_code == 200
        assert response.headers["X-Audit-UserId"] == "audit.user@example.com"
        assert "X-Audit-Timestamp" in response.headers
        assert "X-Content-Safety-Result" in response.headers

    def test_audit_timestamp_header_is_iso8601(self, test_client):
        with patch("api.api_routes.ChartService") as mock_service, patch(
            "api.api_routes.track_event_if_configured"
        ):
            mock_service.return_value.fetch_chart_data = AsyncMock(return_value={"ok": True})

            response = test_client.get("/api/fetchChartData")

        parsed = datetime.fromisoformat(response.headers["X-Audit-Timestamp"])
        assert parsed.tzinfo is not None

    def test_audit_user_header_defaults_to_anonymous(self, test_client):
        with patch("api.api_routes.ChartService") as mock_service, patch(
            "api.api_routes.track_event_if_configured"
        ):
            mock_service.return_value.fetch_chart_data = AsyncMock(return_value={"ok": True})

            response = test_client.get("/api/fetchChartData")

        assert response.headers["X-Audit-UserId"] == "anonymous"

    def test_blocked_content_returns_http_400_and_error_code(self, test_client):
        response = test_client.post(
            "/api/chat",
            headers={"X-Content-Safety-Result": "BLOCKED:Hate"},
            json={"conversation_id": "conv-1", "messages": [{"role": "user", "content": "bad"}]},
        )

        assert response.status_code == 400
        assert response.json()["code"] == "CONTENT_SAFETY_VIOLATION"
        assert response.headers["X-Content-Safety-Result"] == "BLOCKED:Hate"

    def test_blocked_content_response_body_has_required_fields(self, test_client):
        response = test_client.post(
            "/api/chat",
            headers={"X-Content-Safety-Result": "BLOCKED:Violence", "X-APIM-Request-Id": "req-789"},
            json={"conversation_id": "conv-2", "messages": [{"role": "user", "content": "bad"}]},
        )

        body = response.json()
        assert body == {
            "error": "Content blocked by Azure AI Content Safety.",
            "code": "CONTENT_SAFETY_VIOLATION",
            "category": "Violence",
            "requestId": "req-789",
        }

    def test_apim_version_header_defaults_to_3_0(self, test_client):
        with patch("api.api_routes.ChartService") as mock_service, patch(
            "api.api_routes.track_event_if_configured"
        ):
            mock_service.return_value.fetch_chart_data = AsyncMock(return_value={"ok": True})

            response = test_client.get("/api/fetchChartData")

        assert response.headers["X-APIM-Version"] == "3.0"

    def test_empty_chat_body_returns_graceful_400(self, test_client):
        response = test_client.post(
            "/api/chat",
            headers={"Content-Type": "application/json"},
            content="",
        )

        assert response.status_code == 400
        assert response.json()["error"] == "Request body must be a valid JSON object."


class TestPhase4PolicyFiles:
    def test_chat_policy_references_content_safety_named_values(self):
        content = (REPO_ROOT / "infra" / "apim-policies" / "chat-policy.xml").read_text()

        assert "content-safety-endpoint" in content
        # Auth via Managed Identity (passwordless) instead of API key — more secure
        assert "authentication-managed-identity" in content

    def test_phase4_policy_version_is_3_0(self):
        chat_policy = (REPO_ROOT / "infra" / "apim-policies" / "chat-policy.xml").read_text()
        chart_policy = (REPO_ROOT / "infra" / "apim-policies" / "chart-policy.xml").read_text()

        assert "<value>3.0</value>" in chat_policy
        assert "<value>3.0</value>" in chart_policy
