import base64
import json
import sys
import types

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


try:
    import azure.monitor.events.extension  # noqa: F401
except Exception:
    events_module = types.ModuleType("azure.monitor.events")
    extension_module = types.ModuleType("azure.monitor.events.extension")

    def track_event(*args, **kwargs):
        return None

    extension_module.track_event = track_event
    events_module.extension = extension_module
    sys.modules["azure.monitor.events"] = events_module
    sys.modules["azure.monitor.events.extension"] = extension_module

try:
    import azure.monitor.opentelemetry  # noqa: F401
except Exception:
    opentelemetry_module = types.ModuleType("azure.monitor.opentelemetry")

    def configure_azure_monitor(*args, **kwargs):
        return None

    opentelemetry_module.configure_azure_monitor = configure_azure_monitor
    sys.modules["azure.monitor.opentelemetry"] = opentelemetry_module


from api.api_routes import router


def make_principal_header(roles: list[str]) -> str:
    """Create a mock x-ms-client-principal header with given roles."""
    claims = [{"typ": "roles", "val": role} for role in roles]
    claims.append({"typ": "name", "val": "Test User"})
    principal = {
        "auth_typ": "aad",
        "claims": claims,
        "name_typ": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
        "role_typ": "http://schemas.microsoft.com/ws/2008/06/identity/claims/role",
    }
    return base64.b64encode(json.dumps(principal).encode()).decode()


@pytest.fixture
def callcenter_headers():
    return {
        "x-ms-client-principal": make_principal_header(["callcenter"]),
        "x-ms-client-principal-id": "user-001",
        "x-ms-client-principal-name": "operador@contoso.com",
    }


@pytest.fixture
def faturamento_headers():
    return {
        "x-ms-client-principal": make_principal_header(["callcenter", "faturamento"]),
        "x-ms-client-principal-id": "user-002",
        "x-ms-client-principal-name": "financeiro@contoso.com",
    }


@pytest_asyncio.fixture
async def async_client():
    app = FastAPI()
    app.include_router(router)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
