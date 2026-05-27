import asyncio
import json
import logging
import math
import os
import re
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
import requests
from common.config.config import Config
from api.models.input_models import ChartFilters
from api.models.rbac_models import UserInfo
from auth.auth_utils import get_authenticated_user_details, get_tenantid
from auth.rbac import can_access_billing, get_current_user_roles
from services.chat_service import ChatService
from services.chart_service import ChartService
from services.foundry_memory_service import FoundryMemoryService
from common.logging.event_utils import track_event_if_configured
from helpers.azure_credential_utils import get_azure_credential
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

router = APIRouter()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check if the Application Insights Instrumentation Key is set in the environment variables
instrumentation_key = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
if instrumentation_key:
    # Configure Application Insights if the Instrumentation Key is found
    configure_azure_monitor(connection_string=instrumentation_key)
    logging.info("Application Insights configured with the provided Instrumentation Key")
else:
    # Log a warning if the Instrumentation Key is not found
    logging.warning("No Application Insights Instrumentation Key found. Skipping configuration")

# Configure logging
logging.basicConfig(level=logging.INFO)

# Suppress INFO logs from 'azure.core.pipeline.policies.http_logging_policy'
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
    logging.WARNING
)
logging.getLogger("azure.identity.aio._internal").setLevel(logging.WARNING)

# Suppress info logs from OpenTelemetry exporter
logging.getLogger("azure.monitor.opentelemetry.exporter.export._base").setLevel(
    logging.WARNING
)

BILLING_KEYWORDS = [
    r"\bbilling\b",
    r"\bbilling issues?\b",
    r"\bpayments?\b",
    r"\bpayment problems?\b",
    r"\bfaturamento\b",
    r"\bpagamento\b",
    r"\bcobrança\b",
    r"\bcartao de credito\b",
    r"\bcartão de crédito\b",
    r"\bfatura do cartao\b",
    r"\bfatura do cartão\b",
    r"\blimite do cartao\b",
    r"\blimite do cartão\b",
    r"\bbloqueio de cartao\b",
    r"\bbloqueio de cartão\b",
    r"\bcontestacao\b",
    r"\bcontestação\b",
    r"\banuidade\b",
    r"\bcashback\b",
    r"\bpontos do cartao\b",
    r"\bpontos do cartão\b",
    r"\bsegunda via do cartao\b",
    r"\bsegunda via do cartão\b",
]


def _contains_billing_keywords(query: str | None) -> bool:
    if not query:
        return False

    normalized_query = query.casefold()
    return any(re.search(pattern, normalized_query) for pattern in BILLING_KEYWORDS)


def _build_user_info(request: Request) -> UserInfo:
    user_details = get_authenticated_user_details(request.headers)
    roles = get_current_user_roles(request)
    user_principal_id = user_details.get("user_principal_id")
    client_principal_b64 = user_details.get("client_principal_b64")
    tenant_id = get_tenantid(client_principal_b64) or None
    memory_scope = FoundryMemoryService.build_scope(user_principal_id, tenant_id) or None
    return UserInfo(
        user_name=user_details.get("user_name"),
        user_principal_id=user_principal_id,
        roles=roles,
        can_access_billing=can_access_billing(roles),
        tenant_id=tenant_id,
        memory_scope=memory_scope,
    )


@router.get("/fetchChartData")
async def fetch_chart_data():
    try:
        chart_service = ChartService()
        response = await chart_service.fetch_chart_data()
        track_event_if_configured(
            "FetchChartDataSuccess",
            {"status": "success", "source": "/fetchChartData"}
        )
        return JSONResponse(content=response)
    except Exception as e:
        logger.exception("Error in fetch_chart_data: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        return JSONResponse(content={"error": "Failed to fetch chart data due to an internal error."}, status_code=500)


@router.post("/fetchChartDataWithFilters")
async def fetch_chart_data_with_filters(chart_filters: ChartFilters, request: Request):
    try:
        roles = get_current_user_roles(request)
        if not can_access_billing(roles):
            from auth.rbac import RESTRICTED_TOPICS
            chart_filters.selected_filters.Topic = [
                t for t in chart_filters.selected_filters.Topic
                if t not in RESTRICTED_TOPICS
            ]
        filters_json = json.dumps(chart_filters.model_dump(), ensure_ascii=False)
        filters_json = filters_json.replace('\r\n', '').replace('\n', '').replace('\r', '')
        logger.info("Received filters: %s", filters_json)
        chart_service = ChartService()
        response = await chart_service.fetch_chart_data_with_filters(chart_filters)
        track_event_if_configured(
            "FetchChartDataWithFiltersSuccess",
            {"status": "success", "filters": chart_filters.model_dump()}
        )
        # Sanitize the response to handle NaN and Infinity values
        for record in response:
            if isinstance(record.get("chart_value"), list):
                for item in record["chart_value"]:
                    if isinstance(item.get("value"), float) and (math.isnan(item["value"]) or math.isinf(item["value"])):
                        item["value"] = None
        return JSONResponse(content=response)
    except Exception as e:
        logger.exception("Error in fetch_chart_data_with_filters: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        return JSONResponse(content={"error": "Failed to fetch chart data due to an internal error."}, status_code=500)


@router.get("/me", response_model=UserInfo)
async def get_current_user(request: Request) -> UserInfo:
    return _build_user_info(request)


@router.get("/fetchFilterData")
async def fetch_filter_data(request: Request):
    try:
        chart_service = ChartService()
        roles = get_current_user_roles(request)
        response = await chart_service.fetch_filter_data_for_roles(roles)
        track_event_if_configured(
            "FetchFilterDataSuccess",
            {"status": "success", "source": "/fetchFilterData", "roles": roles}
        )
        return JSONResponse(content=response)
    except Exception as e:
        logger.exception("Error in fetch_filter_data: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        return JSONResponse(content={"error": "Failed to fetch filter data due to an internal error."}, status_code=500)


@router.post("/chat")
async def conversation(request: Request):
    try:
        # Get the request JSON and last RAG response from the client
        request_json = await request.json()
        conversation_id = request_json.get("conversation_id")
        messages: list[dict[str, Any]] = request_json.get("messages", [])
        last_message = messages[-1] if messages and isinstance(messages[-1], dict) else {}
        query = last_message.get("content") or ""
        roles = get_current_user_roles(request)

        if _contains_billing_keywords(query) and not can_access_billing(roles):
            logger.warning(
                "Denied billing chat access for user %s with roles %s and query %s",
                get_authenticated_user_details(request.headers).get("user_principal_id"),
                roles,
                query,
            )
            return JSONResponse(
                content={
                    "error": "Acesso negado. As informações sobre Cartão de Crédito (Fatura, Pagamento, Bloqueio e Contestação) requerem o perfil 'financeiro'. Entre em contato com o administrador para solicitar acesso."
                },
                status_code=403,
            )

        chat_service = ChatService(request=request)
        result = await chat_service.stream_chat_request(request_json, conversation_id, query)
        track_event_if_configured(
            "ChatStreamSuccess",
            {"conversation_id": conversation_id, "query": query}
        )
        return StreamingResponse(result, media_type="application/json-lines")

    except Exception as ex:
        logger.exception("Error in conversation endpoint: %s", str(ex))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(ex)
            span.set_status(Status(StatusCode.ERROR, str(ex)))
        return JSONResponse(content={"error": "An internal error occurred while processing the conversation."}, status_code=500)


@router.get("/debug-state")
async def debug_state(request: Request):
    """Debug endpoint to diagnose app state issues."""
    import traceback
    import sys
    result = {
        "python_version": sys.version,
        "agent_present": False,
        "agent_type": None,
        "agent_is_none": None,
        "chat_service_init": "not_tested",
        "classify_query_test": "not_tested",
        "chart_service_init": "not_tested",
        "stream_chat_request_test": "not_tested",
        "errors": [],
    }
    try:
        agent = getattr(request.app.state, "agent", "MISSING")
        result["agent_present"] = agent != "MISSING"
        result["agent_is_none"] = agent is None
        result["agent_type"] = type(agent).__name__
    except Exception as e:
        result["errors"].append(f"agent_state: {traceback.format_exc()}")
    try:
        from helpers.guardrails_enhanced import classify_query, QueryScope
        scope, reason = classify_query("seguro sinistro")
        result["classify_query_test"] = f"{scope.value}: {reason}"
    except Exception as e:
        result["errors"].append(f"classify_query: {traceback.format_exc()}")
    try:
        chat_svc = ChatService(request=request)
        result["chat_service_init"] = "ok"
    except Exception as e:
        result["errors"].append(f"chat_service_init: {traceback.format_exc()}")
    try:
        chart_svc = ChartService()
        result["chart_service_init"] = "ok"
    except Exception as e:
        result["errors"].append(f"chart_service_init: {traceback.format_exc()}")
    try:
        chat_svc2 = ChatService(request=request)
        gen = await chat_svc2.stream_chat_request(
            {"messages": [{"role": "user", "content": "seguro"}], "conversation_id": "debug-test"},
            "debug-test",
            "seguro"
        )
        result["stream_chat_request_test"] = f"ok (type={type(gen).__name__})"
    except Exception as e:
        result["errors"].append(f"stream_chat_request: {traceback.format_exc()}")
    return JSONResponse(content=result)


@router.get("/layout-config")
async def get_layout_config():
    layout_config_str = os.getenv("REACT_APP_LAYOUT_CONFIG", "")
    if layout_config_str:
        try:
            layout_config_json = json.loads(layout_config_str)
            track_event_if_configured("LayoutConfigFetched", {"status": "success"})  # Parse the string into JSON
            return JSONResponse(content=layout_config_json)    # Return the parsed JSON
        except json.JSONDecodeError as e:
            logger.exception("Failed to parse layout config JSON: %s", str(e))
            span = trace.get_current_span()
            if span is not None:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
            return JSONResponse(content={"error": "Invalid layout configuration format."}, status_code=400)
    track_event_if_configured("LayoutConfigNotFound", {})
    return JSONResponse(content={"error": "Layout config not found in environment variables"}, status_code=400)


@router.get("/display-chart-default")
async def get_chart_config():
    chart_config = os.getenv("DISPLAY_CHART_DEFAULT", "")
    if chart_config:
        track_event_if_configured("ChartDisplayDefaultFetched", {"value": chart_config})
        return JSONResponse(content={"isChartDisplayDefault": chart_config})
    track_event_if_configured("ChartDisplayDefaultNotFound", {})
    return JSONResponse(content={"error": "DISPLAY_CHART_DEFAULT flag not found in environment variables"}, status_code=400)


@router.post("/fetch-azure-search-content")
async def fetch_azure_search_content_endpoint(request: Request):
    """
    API endpoint to fetch content from a given URL using the Azure AI Search API.
    Expects a JSON payload with a 'url' field.
    """
    try:
        # Parse the request JSON
        request_json = await request.json()
        url = request_json.get("url")

        if not url:
            return JSONResponse(content={"error": "URL is required"}, status_code=400)

        # Get Azure AD token
        config = Config()
        credential = get_azure_credential(client_id=config.azure_client_id)
        token = credential.get_token("https://search.azure.com/.default")
        access_token = token.token

        # Define blocking request call
        def fetch_content():
            try:
                response = requests.get(
                    url,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    },
                    timeout=10
                )
                if response.status_code == 200:
                    data = response.json()
                    content = data.get("content", "")
                    return content
                else:
                    return f"Error: HTTP {response.status_code}"
            except Exception:
                logger.exception("Exception occurred while making the HTTP request")
                return "Error: Unable to fetch content"

        content = await asyncio.to_thread(fetch_content)

        return JSONResponse(content={"content": content})

    except Exception:
        logger.exception("Error in fetch_azure_search_content_endpoint")
        return JSONResponse(
            content={"error": "Internal server error"},
            status_code=500
        )
