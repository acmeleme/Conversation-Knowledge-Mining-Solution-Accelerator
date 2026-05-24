from unittest.mock import AsyncMock, patch

import pytest


def _chat_payload(query: str) -> dict:
    return {
        "conversation_id": "conv-001",
        "messages": [{"role": "user", "content": query}],
    }


async def _streaming_chunks(*chunks: str):
    for chunk in chunks:
        yield chunk


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "tell me about billing issues",
        "show payment problems",
        "faturamento",
    ],
)
async def test_callcenter_user_cannot_query_chat_for_billing_topics(async_client, callcenter_headers, query):
    with patch("api.api_routes.ChatService") as mock_chat_service:
        response = await async_client.post("/chat", json=_chat_payload(query), headers=callcenter_headers)

    assert response.status_code == 403
    assert "Billing and Payment Issues" in response.json()["error"]
    assert "faturamento role" in response.json()["error"]
    mock_chat_service.assert_not_called()


@pytest.mark.asyncio
async def test_faturamento_user_can_query_chat_for_billing_topics(async_client, faturamento_headers):
    with patch("api.api_routes.ChatService") as mock_chat_service:
        mock_chat_service.return_value.stream_chat_request = AsyncMock(
            return_value=_streaming_chunks('{"message": "billing allowed"}\n\n')
        )

        response = await async_client.post(
            "/chat",
            json=_chat_payload("tell me about billing issues"),
            headers=faturamento_headers,
        )

    assert response.status_code == 200
    assert "billing allowed" in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("fixture_name", ["callcenter_headers", "faturamento_headers"])
async def test_non_billing_queries_work_for_both_roles(async_client, request, fixture_name):
    headers = request.getfixturevalue(fixture_name)

    with patch("api.api_routes.ChatService") as mock_chat_service:
        mock_chat_service.return_value.stream_chat_request = AsyncMock(
            return_value=_streaming_chunks('{"message": "general access"}\n\n')
        )

        response = await async_client.post(
            "/chat",
            json=_chat_payload("show customer sentiment"),
            headers=headers,
        )

    assert response.status_code == 200
    assert "general access" in response.text


@pytest.mark.asyncio
async def test_empty_query_is_not_blocked(async_client, callcenter_headers):
    with patch("api.api_routes.ChatService") as mock_chat_service:
        mock_chat_service.return_value.stream_chat_request = AsyncMock(
            return_value=_streaming_chunks('{"message": "empty still allowed"}\n\n')
        )

        response = await async_client.post("/chat", json=_chat_payload(""), headers=callcenter_headers)

    assert response.status_code == 200
    assert "empty still allowed" in response.text


@pytest.mark.asyncio
async def test_partial_billing_keyword_is_not_blocked(async_client, callcenter_headers):
    with patch("api.api_routes.ChatService") as mock_chat_service:
        mock_chat_service.return_value.stream_chat_request = AsyncMock(
            return_value=_streaming_chunks('{"message": "partial keyword allowed"}\n\n')
        )

        response = await async_client.post("/chat", json=_chat_payload("show bill trends"), headers=callcenter_headers)

    assert response.status_code == 200
    assert "partial keyword allowed" in response.text
