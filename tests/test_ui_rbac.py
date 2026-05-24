from unittest.mock import AsyncMock, patch

import pytest

from auth.rbac import RESTRICTED_TOPIC


FILTER_DATA = [
    {
        "filter_name": "Topic",
        "filter_values": [
            {"displayValue": "Technical Support", "key": "Technical Support"},
            {"displayValue": RESTRICTED_TOPIC, "key": RESTRICTED_TOPIC},
        ],
    },
    {
        "filter_name": "Sentiment",
        "filter_values": [{"displayValue": "Positive", "key": "Positive"}],
    },
]


def _topic_names(payload: list[dict]) -> list[str]:
    topic_filter = next(item for item in payload if item["filter_name"] == "Topic")
    return [value["displayValue"] for value in topic_filter["filter_values"]]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fixture_name", "expected_roles", "can_view_billing", "expected_user"),
    [
        ("callcenter_headers", ["callcenter"], False, "operador@contoso.com"),
        ("faturamento_headers", ["callcenter", "faturamento"], True, "financeiro@contoso.com"),
    ],
)
async def test_me_returns_correct_role_info(async_client, request, fixture_name, expected_roles, can_view_billing, expected_user):
    headers = request.getfixturevalue(fixture_name)

    response = await async_client.get("/me", headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "user_name": expected_user,
        "user_principal_id": headers["x-ms-client-principal-id"],
        "roles": expected_roles,
        "can_access_billing": can_view_billing,
    }


@pytest.mark.asyncio
async def test_callcenter_user_gets_topic_list_without_billing(async_client, callcenter_headers):
    with patch("services.chart_service.adjust_processed_data_dates", new=AsyncMock()), patch(
        "services.chart_service.fetch_filters_data", new=AsyncMock(return_value=FILTER_DATA)
    ):
        response = await async_client.get("/fetchFilterData", headers=callcenter_headers)

    assert response.status_code == 200
    assert RESTRICTED_TOPIC not in _topic_names(response.json())


@pytest.mark.asyncio
async def test_faturamento_user_gets_topic_list_with_billing(async_client, faturamento_headers):
    with patch("services.chart_service.adjust_processed_data_dates", new=AsyncMock()), patch(
        "services.chart_service.fetch_filters_data", new=AsyncMock(return_value=FILTER_DATA)
    ):
        response = await async_client.get("/fetchFilterData", headers=faturamento_headers)

    assert response.status_code == 200
    assert RESTRICTED_TOPIC in _topic_names(response.json())
