import logging
from unittest.mock import patch, MagicMock
import pytest

from common.logging.event_utils import track_event_if_configured, track_metric_if_configured

@pytest.fixture
def event_data():
    return {"user": "test_user", "action": "test_action"}


def test_track_event_with_instrumentation_key(monkeypatch, event_data):
    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "some-key")

    with patch("common.logging.event_utils.track_event") as mock_track_event:
        track_event_if_configured("TestEvent", event_data)
        mock_track_event.assert_called_once_with("TestEvent", event_data)


def test_track_event_without_instrumentation_key(monkeypatch, event_data, caplog):
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)

    with patch("common.logging.event_utils.track_event") as mock_track_event:
        with caplog.at_level(logging.WARNING):
            track_event_if_configured("TestEvent", event_data)
            mock_track_event.assert_not_called()
            assert "Skipping track_event for TestEvent as Application Insights is not configured" in caplog.text


def test_track_metric_with_instrumentation_key(monkeypatch):
    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "some-key")

    mock_counter = MagicMock()
    mock_meter = MagicMock()
    mock_meter.create_counter.return_value = mock_counter

    with patch("common.logging.event_utils.otel_metrics") as mock_otel, \
         patch("common.logging.event_utils._metric_counters", {}):
        mock_otel.get_meter.return_value = mock_meter
        track_metric_if_configured("CKM-TokenUsage", 150.0, {"User ID": "user-1"})

    mock_counter.add.assert_called_once_with(150, {"User ID": "user-1"})


def test_track_metric_reuses_cached_counter(monkeypatch):
    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "some-key")

    mock_counter = MagicMock()
    mock_meter = MagicMock()
    mock_meter.create_counter.return_value = mock_counter

    with patch("common.logging.event_utils.otel_metrics") as mock_otel, \
         patch("common.logging.event_utils._metric_counters", {}):
        mock_otel.get_meter.return_value = mock_meter
        track_metric_if_configured("CKM-TokenUsage", 100.0, {"User ID": "u1"})
        track_metric_if_configured("CKM-TokenUsage", 50.0, {"User ID": "u2"})

    # create_counter should only be called once (counter is cached)
    mock_meter.create_counter.assert_called_once()
    assert mock_counter.add.call_count == 2


def test_track_metric_without_instrumentation_key(monkeypatch, caplog):
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)

    with patch("common.logging.event_utils.otel_metrics") as mock_otel:
        with caplog.at_level(logging.WARNING):
            track_metric_if_configured("CKM-TokenUsage", 150.0, {"User ID": "user-1"})
        mock_otel.get_meter.assert_not_called()
        assert "Skipping track_metric for CKM-TokenUsage as Application Insights is not configured" in caplog.text


def test_track_metric_default_empty_properties(monkeypatch):
    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "some-key")

    mock_counter = MagicMock()
    mock_meter = MagicMock()
    mock_meter.create_counter.return_value = mock_counter

    with patch("common.logging.event_utils.otel_metrics") as mock_otel, \
         patch("common.logging.event_utils._metric_counters", {}):
        mock_otel.get_meter.return_value = mock_meter
        track_metric_if_configured("CKM-TokenUsage", 42.7)

    # value is cast to int, properties defaults to {}
    mock_counter.add.assert_called_once_with(42, {})
