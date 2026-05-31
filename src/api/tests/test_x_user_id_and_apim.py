import logging
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

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


@pytest.mark.parametrize(
    ("headers", "expected_user"),
    [
        ({"X-User-Id": "test@example.com"}, "test@example.com"),
        ({}, "anonymous"),
    ],
)
def test_fetch_chart_data_logs_x_user_id_without_500(test_client, caplog, headers, expected_user):
    with patch("api.api_routes.ChartService") as mock_chart_service, patch(
        "api.api_routes.track_event_if_configured"
    ):
        mock_chart_service.return_value.fetch_chart_data = AsyncMock(return_value={"data": "ok"})

        with caplog.at_level(logging.INFO):
            response = test_client.get("/api/fetchChartData", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"data": "ok"}
    assert f"Request from user: {expected_user} (route=/fetchChartData)" in caplog.text


@patch("helpers.azure_openai_helper.openai.AzureOpenAI")
@patch("helpers.azure_openai_helper.get_bearer_token_provider")
@patch("helpers.azure_openai_helper.get_azure_credential")
def test_get_azure_openai_client_uses_direct_connection_when_apim_disabled(
    mock_get_azure_credential,
    mock_token_provider,
    mock_azure_openai,
    monkeypatch,
):
    monkeypatch.setenv("USE_APIM_GATEWAY", "false")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://direct-openai.example")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-05-01-preview")
    monkeypatch.setenv("AZURE_CLIENT_ID", "client-id")
    monkeypatch.delenv("APIM_ENDPOINT", raising=False)
    monkeypatch.delenv("APIM_SUBSCRIPTION_KEY", raising=False)

    token_provider = Mock(name="token-provider")
    mock_token_provider.return_value = token_provider
    client_instance = Mock(name="direct-client")
    mock_azure_openai.return_value = client_instance

    client = azure_openai_helper.get_azure_openai_client()

    mock_get_azure_credential.assert_called_once_with(client_id="client-id")
    mock_token_provider.assert_called_once()
    mock_azure_openai.assert_called_once_with(
        azure_endpoint="https://direct-openai.example",
        api_version="2024-05-01-preview",
        azure_ad_token_provider=token_provider,
    )
    assert client is client_instance


@patch("helpers.azure_openai_helper.openai.AzureOpenAI")
@patch("helpers.azure_openai_helper.get_bearer_token_provider")
@patch("helpers.azure_openai_helper.get_azure_credential")
def test_get_azure_openai_client_uses_apim_when_enabled(
    mock_get_azure_credential,
    mock_token_provider,
    mock_azure_openai,
    monkeypatch,
):
    monkeypatch.setenv("USE_APIM_GATEWAY", "true")
    monkeypatch.setenv("APIM_ENDPOINT", "https://apim.example.azure-api.net")
    monkeypatch.setenv("APIM_API_VERSION", "2024-02-01")
    monkeypatch.setenv("APIM_SUBSCRIPTION_KEY", "subscription-key")

    client_instance = Mock(name="apim-client")
    mock_azure_openai.return_value = client_instance

    client = azure_openai_helper.get_azure_openai_client()

    mock_get_azure_credential.assert_not_called()
    mock_token_provider.assert_not_called()
    mock_azure_openai.assert_called_once_with(
        azure_endpoint="https://apim.example.azure-api.net",
        api_version="2024-02-01",
        api_key="subscription-key",
        default_headers={"Ocp-Apim-Subscription-Key": "subscription-key"},
    )
    assert client is client_instance


def test_health_endpoint_returns_healthy(test_client):
    response = test_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.parametrize("path", ["/api/fetchFilterData", "/api/fetchChartData"])
def test_post_to_get_only_routes_returns_method_not_allowed(test_client, path):
    response = test_client.post(path, json={})

    assert response.status_code == 405


def test_chat_route_blocks_billing_query_without_billing_role(test_client):
    payload = {
        "conversation_id": "conv-123",
        "messages": [{"content": "billing issue"}],
    }

    response = test_client.post("/api/chat", json=payload)

    assert response.status_code == 403
    assert "Acesso negado" in response.json()["error"]
