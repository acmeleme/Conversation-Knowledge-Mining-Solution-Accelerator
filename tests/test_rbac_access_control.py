from unittest.mock import AsyncMock, patch

import pytest

from auth.auth_utils import can_access_billing, get_user_roles
from auth.rbac import RESTRICTED_TOPIC, filter_topics_by_role
from conftest import make_principal_header


TOPICS = ["Technical Support", RESTRICTED_TOPIC, "Account Management"]
FILTER_DATA = [
    {
        "filter_name": "Topic",
        "filter_values": [
            {"displayValue": "Technical Support", "key": "Technical Support"},
            {"displayValue": RESTRICTED_TOPIC, "key": RESTRICTED_TOPIC},
        ],
    }
]


def _topic_names(payload: list[dict]) -> list[str]:
    topic_filter = next(item for item in payload if item["filter_name"] == "Topic")
    return [value["displayValue"] for value in topic_filter["filter_values"]]


def test_get_user_roles_extracts_callcenter_role():
    headers = {"x-ms-client-principal": make_principal_header(["callcenter"])}

    assert get_user_roles(headers) == ["callcenter"]


def test_get_user_roles_extracts_multiple_roles():
    headers = {"x-ms-client-principal": make_principal_header(["callcenter", "faturamento"])}

    assert get_user_roles(headers) == ["callcenter", "faturamento"]


@pytest.mark.parametrize(
    ("roles", "expected_topics"),
    [
        (["callcenter"], ["Technical Support", "Account Management"]),
        (["callcenter", "faturamento"], TOPICS),
        ([], ["Technical Support", "Account Management"]),
    ],
)
def test_filter_topics_by_role(roles, expected_topics):
    assert filter_topics_by_role(TOPICS, roles) == expected_topics


def test_can_access_billing_denies_callcenter():
    assert can_access_billing(["callcenter"]) is False


def test_can_access_billing_allows_faturamento():
    assert can_access_billing(["callcenter", "faturamento"]) is True


@pytest.mark.asyncio
async def test_no_auth_headers_default_to_callcenter(async_client):
    response = await async_client.get("/me")

    assert response.status_code == 200
    assert response.json()["roles"] == ["callcenter"]
    assert response.json()["can_access_billing"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fixture_name", "billing_visible"),
    [
        (None, False),
        ("callcenter_headers", False),
        ("faturamento_headers", True),
    ],
)
async def test_fetch_filter_data_route_applies_role_protection(async_client, request, fixture_name, billing_visible):
    headers = request.getfixturevalue(fixture_name) if fixture_name else None

    with patch("services.chart_service.adjust_processed_data_dates", new=AsyncMock()), patch(
        "services.chart_service.fetch_filters_data", new=AsyncMock(return_value=FILTER_DATA)
    ):
        response = await async_client.get("/fetchFilterData", headers=headers)

    assert response.status_code == 200
    topics = _topic_names(response.json())
    assert (RESTRICTED_TOPIC in topics) is billing_visible
