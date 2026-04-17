import sys
import os
SRC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../src'))
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)
import pytest
pytestmark = pytest.mark.asyncio
from fastapi import Request
from src.api.services.chat_service import ChatService
from starlette.datastructures import State
from types import SimpleNamespace
from src.api.helpers.guardrails import is_in_scope
import asyncio


class DummyAgent:
    client = None
    async def invoke_stream(self, messages, thread=None, truncation_strategy=None):
        class DummyResponse:
            def __init__(self, content):
                self.content = content
                self.thread = type('T', (), {'id': 'dummy-thread'})
            def __str__(self):
                return self.content
        # Simula uma resposta do agente
        yield DummyResponse("Sim, o nível de satisfação dos clientes está alto.")

def make_request():
    req = SimpleNamespace()
    req.app = SimpleNamespace()
    req.app.state = State()
    req.app.state.agent = DummyAgent()
    return req

@pytest.mark.asyncio
async def test_stream_openai_text_out_of_scope():
    req = make_request()
    chat_service = ChatService(req)
    conversation_id = "test_conv"
    query = "Como fazer um bolo de chocolate?"
    gen = chat_service.stream_openai_text(conversation_id, query)
    result = ""
    async for chunk in gen:
        result += chunk
    assert "I am only allowed to answer questions about customer satisfaction and call analysis" in result

@pytest.mark.asyncio
async def test_stream_openai_text_in_scope():
    req = make_request()
    chat_service = ChatService(req)
    conversation_id = "test_conv"
    query = "Qual o nível de satisfação dos clientes?"
    # Simula o fluxo até o guardrail (não executa LLM real)
    # O guardrail não bloqueia, então o fluxo seguiria normalmente (aqui não testamos integração LLM)
    gen = chat_service.stream_openai_text(conversation_id, query)
    # Não deve retornar a mensagem de bloqueio logo de cara
    chunk = await gen.__anext__()
    assert "I am only allowed to answer questions about customer satisfaction and call analysis" not in chunk
