"""Utility functions for tracking events and metrics with Azure Monitor Application Insights.

This module provides helper functions to log custom events and custom metrics to Azure
Application Insights, if the instrumentation key is configured in the environment.
"""

import logging
import os
from azure.monitor.events.extension import track_event
from opentelemetry import metrics as otel_metrics

# Cache of OTel counters keyed by metric name, populated lazily on first use.
_metric_counters: dict = {}


def track_event_if_configured(event_name: str, event_data: dict):
    instrumentation_key = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    print(f"Instrumentation Key: {instrumentation_key}")
    if instrumentation_key:
        track_event(event_name, event_data)
    else:
        logging.warning(f"Skipping track_event for {event_name} as Application Insights is not configured")


def track_metric_if_configured(metric_name: str, value: float, properties: dict = None):
    """Emit a custom metric to Azure Application Insights (customMetrics table).

    Uses the OpenTelemetry Counter API; ``azure-monitor-opentelemetry`` exports the
    accumulated counter values to the App Insights ``customMetrics`` table automatically.
    The meter is obtained lazily so this function is safe to call before
    ``configure_azure_monitor()`` has been invoked (e.g. during import time), but the
    metric will only be exported once the OTel pipeline is active.

    A no-op when ``APPLICATIONINSIGHTS_CONNECTION_STRING`` is not set.
    """
    if not os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        logging.warning(f"Skipping track_metric for {metric_name} as Application Insights is not configured")
        return

    if metric_name not in _metric_counters:
        meter = otel_metrics.get_meter("ckm-api")
        _metric_counters[metric_name] = meter.create_counter(
            name=metric_name,
            unit="tokens",
            description=f"Custom metric: {metric_name}",
        )

    _metric_counters[metric_name].add(int(value), properties or {})
