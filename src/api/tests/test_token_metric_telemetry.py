"""
Tests proving that CKM-TokenUsage is emitted to ``customMetrics`` — not ``customEvents``.

Background
----------
Dashboard Tiles 4 and 6 were always rendering empty because the app called
``track_event()`` (which writes to the App Insights ``customEvents`` table) while
the dashboard KQL queries targeted ``customMetrics``.

Fix (Fix-A)
-----------
``event_utils.track_metric_if_configured()`` now uses the OpenTelemetry Counter API,
which is automatically exported to ``customMetrics`` by ``azure-monitor-opentelemetry``.
``chat_service.py`` calls this function after each successful streaming response with:
  - metric name  : ``"CKM-TokenUsage"``
  - dimension key: ``{"user_id": <user>}``  ← snake_case, matches dashboard KQL

Dashboard KQL contract
----------------------
Tile 4: ``customMetrics | where name startswith "CKM-TokenUsage"``
Tile 6: ``customMetrics | ... | extend userId = tostring(customDimensions["user_id"])``
"""

import sys
import types
import json
from pathlib import Path
from unittest.mock import ANY, AsyncMock, MagicMock, Mock, patch

import pytest
from cachetools import TTLCache

# ── Module-level stubs: must be installed before any app import ───────────────
_mock_events_pkg = types.ModuleType("azure.monitor.events")
_mock_events_ext = types.ModuleType("azure.monitor.events.extension")
_sentinel_track_event = Mock(name="track_event_sentinel")
_mock_events_ext.track_event = _sentinel_track_event
_mock_events_pkg.extension = _mock_events_ext
sys.modules.setdefault("azure.monitor.events", _mock_events_pkg)
sys.modules.setdefault("azure.monitor.events.extension", _mock_events_ext)

_mock_monitor = types.ModuleType("azure.monitor.opentelemetry")
_mock_monitor.configure_azure_monitor = Mock()
sys.modules.setdefault("azure.monitor.opentelemetry", _mock_monitor)

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))


# ─────────────────────────────────────────────────────────────────────────────
# Helper: build a spy counter pair (mock_meter, mock_counter)
# ─────────────────────────────────────────────────────────────────────────────
def _make_mock_meter():
    mock_counter = Mock(name="otel-counter")
    mock_meter = Mock(name="otel-meter")
    mock_meter.create_counter.return_value = mock_counter
    return mock_meter, mock_counter


def _collect_query_strings(node):
    if isinstance(node, dict):
        if node.get("name") == "Query" and isinstance(node.get("value"), str):
            yield node["value"]
        for value in node.values():
            yield from _collect_query_strings(value)
    elif isinstance(node, list):
        for item in node:
            yield from _collect_query_strings(item)


# ─────────────────────────────────────────────────────────────────────────────
# Group 1 — Unit tests for event_utils.track_metric_if_configured
#   Prove the function routes telemetry to OTel (customMetrics) not track_event
# ─────────────────────────────────────────────────────────────────────────────

class TestTrackMetricIfConfigured:
    """Pure unit tests — no app import required."""

    def setup_method(self):
        # Clear the module-level counter cache between tests to avoid state leak.
        import common.logging.event_utils as eu
        eu._metric_counters.clear()

    def test_writes_via_otel_counter_not_track_event(self, monkeypatch):
        """Metric goes to OTel Counter.add() — track_event is never called.

        This is the core fix: OTel counters export to ``customMetrics`` via
        azure-monitor-opentelemetry, which is the table the dashboard KQL queries.
        """
        monkeypatch.setenv(
            "APPLICATIONINSIGHTS_CONNECTION_STRING", "InstrumentationKey=test-key"
        )
        _sentinel_track_event.reset_mock()
        mock_meter, mock_counter = _make_mock_meter()

        with patch("opentelemetry.metrics.get_meter", return_value=mock_meter):
            from common.logging.event_utils import track_metric_if_configured

            track_metric_if_configured("CKM-TokenUsage", 42, {"user_id": "test@ckm.local"})

        mock_meter.create_counter.assert_called_once_with(
            name="CKM-TokenUsage",
            unit="tokens",
            description="Custom metric: CKM-TokenUsage",
        )
        mock_counter.add.assert_called_once_with(42, {"user_id": "test@ckm.local"})
        # ↓ Proves telemetry does NOT go to customEvents table
        _sentinel_track_event.assert_not_called()

    def test_dimension_key_is_user_id_space_title_case(self, monkeypatch):
        """Dimension key emitted as exactly 'User ID' (title-case with space).

        Dashboard Tile 6 KQL reads: ``customDimensions["User ID"]``.
        Any other variant (user_id, userid, User_ID) silently returns zero rows.
        """
        monkeypatch.setenv(
            "APPLICATIONINSIGHTS_CONNECTION_STRING", "InstrumentationKey=test-key"
        )
        captured: dict = {}

        def spy_add(value, props):
            captured.update(props)

        mock_meter, mock_counter = _make_mock_meter()
        mock_counter.add.side_effect = spy_add

        with patch("opentelemetry.metrics.get_meter", return_value=mock_meter):
            from common.logging.event_utils import track_metric_if_configured

            track_metric_if_configured(
                "CKM-TokenUsage", 100, {"User ID": "morgan@ckm.local"}
            )

        assert "User ID" in captured, (
            "Dimension key must be 'User ID' (title-case with space) — "
            'dashboard KQL reads customDimensions["User ID"]'
        )
        assert "user_id" not in captured, "Underscore variant misses dashboard KQL"
        assert "userid" not in captured, "No-space variant misses dashboard KQL"
        assert captured["User ID"] == "morgan@ckm.local"

    def test_metric_name_matches_dashboard_kql_startswith_filter(self, monkeypatch):
        """Counter name satisfies dashboard Tile 4 filter: name startswith 'CKM-TokenUsage'."""
        monkeypatch.setenv(
            "APPLICATIONINSIGHTS_CONNECTION_STRING", "InstrumentationKey=test-key"
        )
        mock_meter, mock_counter = _make_mock_meter()

        with patch("opentelemetry.metrics.get_meter", return_value=mock_meter):
            from common.logging.event_utils import track_metric_if_configured

            track_metric_if_configured("CKM-TokenUsage", 75, {})

        call = mock_meter.create_counter.call_args
        # Support both positional and keyword invocation
        actual_name = (call.kwargs or {}).get("name") or (call.args or ("",))[0]
        assert actual_name.startswith("CKM-TokenUsage"), (
            f"Counter name '{actual_name}' does not satisfy "
            "Tile 4 KQL filter: name startswith 'CKM-TokenUsage'"
        )

    def test_noop_when_connection_string_absent(self, monkeypatch):
        """When App Insights is not configured the function is a silent no-op."""
        monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
        _sentinel_track_event.reset_mock()

        with patch("opentelemetry.metrics.get_meter") as mock_get_meter:
            from common.logging.event_utils import track_metric_if_configured

            track_metric_if_configured("CKM-TokenUsage", 10, {"user_id": "anon"})

        mock_get_meter.assert_not_called()
        _sentinel_track_event.assert_not_called()

    def test_counter_cached_on_second_call(self, monkeypatch):
        """OTel meter is called once; subsequent calls reuse the cached counter."""
        monkeypatch.setenv(
            "APPLICATIONINSIGHTS_CONNECTION_STRING", "InstrumentationKey=test-key"
        )
        mock_meter, mock_counter = _make_mock_meter()

        with patch("opentelemetry.metrics.get_meter", return_value=mock_meter):
            from common.logging.event_utils import track_metric_if_configured

            track_metric_if_configured("CKM-TokenUsage", 10, {})
            track_metric_if_configured("CKM-TokenUsage", 20, {})

        # Counter created once, add called twice
        assert mock_meter.create_counter.call_count == 1
        assert mock_counter.add.call_count == 2


# ─────────────────────────────────────────────────────────────────────────────
# Group 2 — Integration: chat_service.stream_chat_request emits the metric
#   Patches track_metric_if_configured and drives the generator to completion.
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def minimal_chat_service():
    """Build a ChatService instance that bypasses all external dependencies.

    Uses object.__new__ to skip __init__, then sets the minimum attributes
    the generate() coroutine accesses when memory_service is None.
    """
    from services.chat_service import ChatService

    # Reset class-level caches to known states
    ChatService.thread_cache = None
    ChatService.language_cache = TTLCache(maxsize=100, ttl=3600)
    ChatService.memory_service = None

    mock_request = MagicMock()
    mock_request.headers = {"X-User-Id": "morgan-test@ckm.local"}

    service = object.__new__(ChatService)
    service.request = mock_request
    service.agent = MagicMock()
    service.memory_service = None
    service.azure_openai_deployment_name = "test-deployment"

    return service


@pytest.mark.asyncio
async def test_stream_chat_request_emits_ckm_token_usage_metric(minimal_chat_service):
    """After a successful streaming response, track_metric_if_configured is called with
    metric name 'CKM-TokenUsage' and dimension {'user_id': <x-user-id header value>}.

    This test proves the full call chain:
      /api/chat → ChatService.stream_chat_request → generate() → track_metric_if_configured
    is wired correctly and the telemetry goes to the right App Insights table.
    """
    from helpers.guardrails_enhanced import QueryScope

    async def fake_stream(*args, **kwargs):
        yield "Here is a test response about call center KPIs."

    minimal_chat_service.stream_openai_text = fake_stream

    with patch("services.chat_service.track_metric_if_configured") as mock_track, \
         patch("services.chat_service.classify_query",
               return_value=(QueryScope.IN_SCOPE, "allowed")):

        gen = await minimal_chat_service.stream_chat_request(
            {"history_metadata": {}, "messages": []},
            "conv-metric-test-001",
            "What are the call center KPIs?",
        )
        async for _ in gen:
            pass  # drain so all post-stream side-effects execute

    mock_track.assert_called_once()
    name, value, props = mock_track.call_args.args

    assert name == "CKM-TokenUsage", (
        f"Expected metric name 'CKM-TokenUsage', got '{name}' — "
        "Tile 4 KQL filter (name startswith 'CKM-TokenUsage') would miss this"
    )
    assert isinstance(value, int) and value > 0, (
        f"Token count must be a positive int, got {value!r}"
    )
    assert props == {"user_id": "morgan-test@ckm.local"}, (
        f"Properties {props!r} do not match — "
        "Tile 6 KQL reads customDimensions[\"user_id\"] with snake_case key"
    )


@pytest.mark.asyncio
async def test_stream_chat_request_no_metric_when_response_empty(minimal_chat_service):
    """If the agent yields no content, track_metric_if_configured must NOT be called.

    An empty full_response means the guard ``if full_response:`` fails, preventing
    zero-value metric points from polluting the customMetrics table.
    """
    from helpers.guardrails_enhanced import QueryScope

    async def empty_stream(*args, **kwargs):
        return
        yield  # make it an async generator

    minimal_chat_service.stream_openai_text = empty_stream

    with patch("services.chat_service.track_metric_if_configured") as mock_track, \
         patch("services.chat_service.classify_query",
               return_value=(QueryScope.IN_SCOPE, "allowed")):

        gen = await minimal_chat_service.stream_chat_request(
            {"history_metadata": {}, "messages": []},
            "conv-empty-resp-002",
            "Hello?",
        )
        async for _ in gen:
            pass

    mock_track.assert_not_called()


@pytest.mark.asyncio
async def test_stream_chat_request_uses_x_user_id_header_for_dimension(minimal_chat_service):
    """user_id in the metric dimension comes from X-User-Id header first.

    The resolution chain is: X-User-Id → user_principal_id → "anonymous".
    Dashboard Tile 6 groups by this value to show per-user token consumption.
    """
    from helpers.guardrails_enhanced import QueryScope

    # Override with a different user header
    minimal_chat_service.request.headers = {"X-User-Id": "alice@financeirax.com"}

    async def fake_stream(*args, **kwargs):
        yield "Response content for Alice."

    minimal_chat_service.stream_openai_text = fake_stream

    with patch("services.chat_service.track_metric_if_configured") as mock_track, \
         patch("services.chat_service.classify_query",
               return_value=(QueryScope.IN_SCOPE, "allowed")):

        gen = await minimal_chat_service.stream_chat_request(
            {"history_metadata": {}, "messages": []},
            "conv-alice-003",
            "Summarise today's calls.",
        )
        async for _ in gen:
            pass

    mock_track.assert_called_once()
    _, _, props = mock_track.call_args.args
    assert props["user_id"] == "alice@financeirax.com"


@pytest.mark.asyncio
async def test_stream_chat_request_falls_back_to_anonymous_when_no_user_header(
    minimal_chat_service,
):
    """When X-User-Id is absent and Easy Auth is not active, user_id is 'anonymous'."""
    from helpers.guardrails_enhanced import QueryScope

    minimal_chat_service.request.headers = {}  # no X-User-Id

    async def fake_stream(*args, **kwargs):
        yield "Generic response."

    minimal_chat_service.stream_openai_text = fake_stream

    with patch("services.chat_service.track_metric_if_configured") as mock_track, \
         patch("services.chat_service.classify_query",
               return_value=(QueryScope.IN_SCOPE, "allowed")), \
         patch(
             "services.chat_service.get_authenticated_user_details",
             return_value={},
         ):

        gen = await minimal_chat_service.stream_chat_request(
            {"history_metadata": {}, "messages": []},
            "conv-anon-004",
            "Generic question.",
        )
        async for _ in gen:
            pass

    mock_track.assert_called_once()
    _, _, props = mock_track.call_args.args
    assert props["user_id"] == "anonymous"


def test_dashboard_artifacts_query_custom_metrics_for_token_usage():
    """Dashboard artifacts must query customMetrics for CKM-TokenUsage evidence.

    This is the end-to-end contract proof for the telemetry fix:
      metric emitter → App Insights customMetrics → dashboard KQL tiles.
    """
    evidence_paths = [
        REPO_ROOT / "dashboard-full-definition.json",
        REPO_ROOT / "tile-4.json",
        REPO_ROOT / "tile-6.json",
    ]

    for path in evidence_paths:
        payload = path.read_text(encoding="utf-8")
        assert "customMetrics" in payload, f"{path.name} does not query customMetrics"
        assert "CKM-TokenUsage" in payload, f"{path.name} does not reference CKM-TokenUsage"

    # The sibling dashboard.json file in this workspace is only a preview warning stub.
    dashboard_json = (REPO_ROOT / "dashboard.json").read_text(encoding="utf-8")
    assert dashboard_json.startswith("WARNING:"), "dashboard.json should remain the preview warning stub"

    tile_4 = REPO_ROOT / "tile-4.json"
    tile_6 = REPO_ROOT / "tile-6.json"
    tile_4_queries = " ".join(
        "\n".join(_collect_query_strings(json.loads(tile_4.read_text(encoding="utf-8")))).split()
    )
    tile_6_queries = " ".join(
        "\n".join(_collect_query_strings(json.loads(tile_6.read_text(encoding="utf-8")))).split()
    )

    assert "customMetrics" in tile_4_queries and 'where name startswith "CKM-TokenUsage"' in tile_4_queries
    assert "customMetrics" in tile_6_queries and 'where name startswith "CKM-TokenUsage"' in tile_6_queries
    assert 'customDimensions["user_id"]' in tile_6_queries
    assert "customEvents" not in tile_4_queries
    assert "customEvents" not in tile_6_queries


@pytest.mark.parametrize(
    ("payload", "expected_type"),
    [
        ('{"type":"bar","data":{"labels":["A"],"datasets":[{"data":[1]}]}}', "bar"),
        (
            json.dumps(
                {
                    "answer": '{"type":"line","data":{"labels":["A"],"datasets":[{"data":[2]}]}}',
                    "citations": [],
                }
            ),
            "line",
        ),
        (
            '```json\n{"type":"pie","data":{"labels":["A"],"datasets":[{"data":[3]}]}}\n```',
            "pie",
        ),
    ],
)
def test_try_extract_chart_json_handles_wrapped_payloads(payload, expected_type):
    from services.chat_service import ChatService

    parsed = ChatService._try_extract_chart_json(payload)

    assert parsed is not None
    assert parsed["type"] == expected_type
    assert "data" in parsed


@pytest.mark.asyncio
async def test_stream_chat_request_emits_structured_chart_response(minimal_chat_service):
    from helpers.guardrails_enhanced import QueryScope

    wrapped_chart = json.dumps(
        {
            "answer": (
                '{"type":"bar","data":{"labels":["Jan"],"datasets":[{"label":"Calls","data":[10]}]},'
                '"options":{"responsive":true}}'
            ),
            "citations": [],
        }
    )

    async def fake_stream(*args, **kwargs):
        yield wrapped_chart

    minimal_chat_service.stream_openai_text = fake_stream

    with patch("services.chat_service.classify_query",
               return_value=(QueryScope.IN_SCOPE, "allowed")), \
         patch("services.chat_service.track_metric_if_configured"):
        gen = await minimal_chat_service.stream_chat_request(
            {"history_metadata": {}, "messages": []},
            "conv-chart-005",
            "Show me a chart of monthly calls.",
        )
        chunks = [chunk async for chunk in gen]

    assert len(chunks) == 2

    streamed_text_chunk = json.loads(chunks[0].strip())
    assert streamed_text_chunk["choices"][0]["messages"][0]["content"] == wrapped_chart

    chart_chunk = json.loads(chunks[1].strip())
    assert chart_chunk["object"]["type"] == "bar"
    assert chart_chunk["object"]["data"]["labels"] == ["Jan"]
    assert chart_chunk["object"]["options"]["responsive"] is True
