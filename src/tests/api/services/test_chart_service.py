import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock, MagicMock, patch


@patch("common.database.sqldb_service.adjust_processed_data_dates", new_callable=MagicMock)
@patch("common.database.sqldb_service.fetch_filters_data", new_callable=MagicMock)
@patch("common.database.sqldb_service.fetch_chart_data", new_callable=AsyncMock)
@patch("api.models.input_models.ChartFilters", new_callable=MagicMock)
@pytest.fixture
def patched_imports(_, __, ___, ____):
    """
    Apply patches to dependencies before importing ChartService.
    Returns patched ChartService
    """
    with patch("services.chart_service.adjust_processed_data_dates"), \
         patch("services.chart_service.fetch_filters_data"), \
         patch("services.chart_service.fetch_chart_data"), \
         patch("services.chart_service.filter_topics_by_role"):
        from services.chart_service import ChartService
        return ChartService


with patch("common.database.sqldb_service.adjust_processed_data_dates", MagicMock()), \
     patch("common.database.sqldb_service.fetch_filters_data", MagicMock()), \
     patch("common.database.sqldb_service.fetch_chart_data", AsyncMock()), \
     patch("api.models.input_models.ChartFilters", MagicMock()):
    from services.chart_service import ChartService


@pytest.fixture
def chart_service():
    return ChartService()


@patch("services.chart_service.adjust_processed_data_dates", new_callable=AsyncMock)
@patch("services.chart_service.fetch_filters_data", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_fetch_filter_data_success(mock_fetch_filters_data, mock_adjust_dates, chart_service):
    mock_adjust_dates.return_value = None
    mock_fetch_filters_data.return_value = {"data": "filter_data"}

    result = await chart_service.fetch_filter_data()
    assert result == {"data": "filter_data"}


@patch("services.chart_service.adjust_processed_data_dates", new_callable=AsyncMock, side_effect=Exception("Failed"))
@patch("services.chart_service.fetch_filters_data", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_fetch_filter_data_failure(mock_fetch_filters_data, mock_adjust_dates, chart_service):
    with pytest.raises(HTTPException) as exc_info:
        await chart_service.fetch_filter_data()
    assert exc_info.value.status_code == 500


@patch("services.chart_service.adjust_processed_data_dates", new_callable=AsyncMock)
@patch("services.chart_service.fetch_filters_data", new_callable=AsyncMock)
@patch("services.chart_service.filter_topics_by_role")
@pytest.mark.asyncio
async def test_fetch_filter_data_for_roles_filters_restricted_topic(
    mock_filter_topics_by_role,
    mock_fetch_filters_data,
    mock_adjust_dates,
    chart_service,
):
    mock_adjust_dates.return_value = None
    mock_fetch_filters_data.return_value = [
        {
            "filter_name": "Topic",
            "filter_values": [
                {"displayValue": "General Support", "key": "General Support"},
                {"displayValue": "Billing and Payment Issues", "key": "Billing and Payment Issues"},
            ],
        },
        {
            "filter_name": "Sentiment",
            "filter_values": [{"displayValue": "Positive", "key": "Positive"}],
        },
    ]
    mock_filter_topics_by_role.return_value = ["General Support"]

    result = await chart_service.fetch_filter_data_for_roles(["callcenter"])

    assert result == [
        {
            "filter_name": "Topic",
            "filter_values": [{"displayValue": "General Support", "key": "General Support"}],
        },
        {
            "filter_name": "Sentiment",
            "filter_values": [{"displayValue": "Positive", "key": "Positive"}],
        },
    ]
    mock_filter_topics_by_role.assert_called_once_with(
        ["General Support", "Billing and Payment Issues"], ["callcenter"]
    )


@patch("services.chart_service.adjust_processed_data_dates", new_callable=AsyncMock)
@patch("services.chart_service.fetch_filters_data", new_callable=AsyncMock)
@patch("services.chart_service.filter_topics_by_role")
@pytest.mark.asyncio
async def test_fetch_filter_data_for_roles_keeps_restricted_topic_for_faturamento(
    mock_filter_topics_by_role,
    mock_fetch_filters_data,
    mock_adjust_dates,
    chart_service,
):
    mock_adjust_dates.return_value = None
    mock_fetch_filters_data.return_value = [
        {
            "filter_name": "Topic",
            "filter_values": [
                {"displayValue": "General Support", "key": "General Support"},
                {"displayValue": "Billing and Payment Issues", "key": "Billing and Payment Issues"},
            ],
        }
    ]
    mock_filter_topics_by_role.return_value = ["General Support", "Billing and Payment Issues"]

    result = await chart_service.fetch_filter_data_for_roles(["faturamento"])

    assert result == [
        {
            "filter_name": "Topic",
            "filter_values": [
                {"displayValue": "General Support", "key": "General Support"},
                {"displayValue": "Billing and Payment Issues", "key": "Billing and Payment Issues"},
            ],
        }
    ]


@patch("services.chart_service.adjust_processed_data_dates", new_callable=AsyncMock, side_effect=Exception("Failed"))
@patch("services.chart_service.fetch_filters_data", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_fetch_filter_data_for_roles_failure(mock_fetch_filters_data, mock_adjust_dates, chart_service):
    with pytest.raises(HTTPException) as exc_info:
        await chart_service.fetch_filter_data_for_roles(["callcenter"])
    assert exc_info.value.status_code == 500


@patch("services.chart_service.fetch_chart_data", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_fetch_chart_data_success(mock_fetch_chart_data, chart_service):
    mock_fetch_chart_data.return_value = {"data": "chart_data"}
    result = await chart_service.fetch_chart_data()
    assert result == {"data": "chart_data"}


@patch("services.chart_service.fetch_chart_data", new_callable=AsyncMock, side_effect=Exception("DB error"))
@pytest.mark.asyncio
async def test_fetch_chart_data_failure(mock_fetch_chart_data, chart_service):
    with pytest.raises(HTTPException) as exc_info:
        await chart_service.fetch_chart_data()
    assert exc_info.value.status_code == 500


@patch("services.chart_service.fetch_chart_data", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_fetch_chart_data_with_filters_success(mock_fetch_chart_data, chart_service):
    mock_fetch_chart_data.return_value = {"data": "filtered_chart_data"}
    fake_filters = MagicMock()

    result = await chart_service.fetch_chart_data_with_filters(fake_filters)
    assert result == {"data": "filtered_chart_data"}


@patch("services.chart_service.fetch_chart_data", new_callable=AsyncMock, side_effect=Exception("Failure"))
@pytest.mark.asyncio
async def test_fetch_chart_data_with_filters_failure(mock_fetch_chart_data, chart_service):
    fake_filters = MagicMock()

    with pytest.raises(HTTPException) as exc_info:
        await chart_service.fetch_chart_data_with_filters(fake_filters)
    assert exc_info.value.status_code == 500
