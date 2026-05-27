import asyncio
import base64
import json
from types import SimpleNamespace

import pytest
from starlette.datastructures import State

from src.api.services.chat_service import ChatService
from src.api.services.foundry_memory_service import FoundryMemoryService


class DummyAgent:
    def __init__(self):
        self.client = None
        self.invocations = []

    async def invoke_stream(self, messages, thread=None, truncation_strategy=None):
        self.invocations.append(messages)

        class DummyResponse:
            def __init__(self, content):
                self.content = content
                self.thread = type("T", (), {"id": "dummy-thread"})

        yield DummyResponse('{"answer":"Memory-aware response","citations":[]}')


class DummyMemoryService:
    def __init__(self):
        self.search_calls = []
        self.update_calls = []

    @staticmethod
    def build_scope(user_principal_id, tenant_id):
        return FoundryMemoryService.build_scope(user_principal_id, tenant_id)

    async def search_context(self, scope, query):
        self.search_calls.append((scope, query))
        return "Relevant prior user memories:\n- Customer prefers concise summaries"

    async def update_from_turn(self, scope, user_text, assistant_text):
        self.update_calls.append((scope, user_text, assistant_text))


def _make_client_principal_header(tenant_id: str) -> str:
    principal = {
        "auth_typ": "aad",
        "claims": [
            {"typ": "tid", "val": tenant_id},
            {"typ": "name", "val": "Test User"},
        ],
        "name_typ": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
        "role_typ": "http://schemas.microsoft.com/ws/2008/06/identity/claims/role",
    }
    return base64.b64encode(json.dumps(principal).encode()).decode()


def make_request(agent: DummyAgent):
    req = SimpleNamespace()
    req.app = SimpleNamespace()
    req.app.state = State()
    req.app.state.agent = agent
    req.headers = {
        "x-ms-client-principal-id": "user-123",
        "x-ms-client-principal": _make_client_principal_header("tenant-456"),
    }
    return req


@pytest.mark.asyncio
async def test_stream_chat_request_injects_memory_context_and_updates_after_response():
    agent = DummyAgent()
    memory_service = DummyMemoryService()
    ChatService.thread_cache = None
    ChatService.language_cache = None
    ChatService.memory_service = memory_service

    chat_service = ChatService(make_request(agent))
    request_body = {
        "conversation_id": "conv-memory",
        "messages": [{"role": "user", "content": "Summarize the latest escalations"}],
        "history_metadata": {},
    }

    stream = await chat_service.stream_chat_request(
        request_body,
        "conv-memory",
        "Summarize the latest escalations",
    )
    chunks = []
    async for chunk in stream:
        chunks.append(chunk)

    await asyncio.sleep(0)

    scope = FoundryMemoryService.build_scope("user-123", "tenant-456")
    assert memory_service.search_calls == [(scope, "Summarize the latest escalations")]
    assert memory_service.update_calls == [
        (scope, "Summarize the latest escalations", '{"answer":"Memory-aware response","citations":[]}')
    ]
    assert agent.invocations
    assert "Relevant prior user memories" in agent.invocations[0]
    assert "Current user question" in agent.invocations[0]
    assert any("Memory-aware response" in chunk for chunk in chunks)


def test_build_scope_sanitizes_and_stabilizes_identity_values():
    scope = FoundryMemoryService.build_scope("user:123", "tenant/456")
    assert scope == "tenant_tenant_456__user_user_123"
    assert FoundryMemoryService.build_scope("", "tenant-456") == ""
