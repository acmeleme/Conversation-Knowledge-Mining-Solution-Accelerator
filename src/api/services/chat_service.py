"""
Provides the ChatService class and related utilities for handling chat interactions,
streaming responses, RAG (Retrieval-Augmented Generation) processing, and chart data
generation for visualization in a call center knowledge mining solution.

Includes thread management, caching, and integration with Azure OpenAI and FastAPI.
"""

import json
import logging
import time
import uuid
from types import SimpleNamespace
import asyncio
import random
import re
from typing import Optional


from fastapi import HTTPException, Request, status
from fastapi.responses import StreamingResponse

# Guardrails - Enhanced multi-layer protection
from helpers.guardrails_enhanced import classify_query, QueryScope, get_guardrail_message

from semantic_kernel.agents import AzureAIAgentThread
from semantic_kernel.exceptions.agent_exceptions import AgentException

from azure.ai.agents.models import TruncationObject

from cachetools import TTLCache

from auth.auth_utils import get_authenticated_user_details, get_tenantid
from helpers.utils import format_stream_response
from common.config.config import Config
from services.foundry_memory_service import FoundryMemoryService

# Constants
HOST_NAME = "CKM"
HOST_INSTRUCTIONS = "Answer questions about call center operations"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExpCache(TTLCache):
    """
    Extended TTLCache that associates an agent and deletes Azure AI agent threads when items expire or are evicted (LRU).
    """
    def __init__(self, *args, agent=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.agent = agent

    def expire(self, time=None):
        items = super().expire(time)
        for key, thread_id in items:
            try:
                if self.agent:
                    thread = AzureAIAgentThread(client=self.agent.client, thread_id=thread_id)
                    asyncio.create_task(thread.delete())
                    print(f"Thread deleted : {thread_id}")
            except Exception as e:
                logger.error("Failed to delete thread for key %s: %s", key, e)
        return items

    def popitem(self):
        key, thread_id = super().popitem()
        try:
            if self.agent:
                thread = AzureAIAgentThread(client=self.agent.client, thread_id=thread_id)
                asyncio.create_task(thread.delete())
                print(f"Thread deleted (LRU evict): {thread_id}")
        except Exception as e:
            logger.error("Failed to delete thread for key %s (LRU evict): %s", key, e)
        return key, thread_id


class ChatService:
    """
    Service for handling chat interactions, including streaming responses,
    processing RAG responses, and generating chart data for visualization.
    """

    thread_cache = None
    language_cache = None
    memory_service = None

    def __init__(self, request : Request):
        config = Config()
        self.azure_openai_deployment_name = config.azure_openai_deployment_model
        self.agent = request.app.state.agent
        self.request = request

        if ChatService.thread_cache is None:
            ChatService.thread_cache = ExpCache(maxsize=1000, ttl=3600.0, agent=self.agent)
        if ChatService.language_cache is None:
            ChatService.language_cache = TTLCache(maxsize=5000, ttl=24 * 3600)
        if ChatService.memory_service is None:
            ChatService.memory_service = FoundryMemoryService()
        self.memory_service = ChatService.memory_service

    @staticmethod
    def _detect_language(text: str) -> str:
        """Detect preferred response language from first user interaction."""
        if not text:
            return "en"

        text_norm = text.lower()
        if re.search(r"[\u00e0-\u00ff]", text_norm):
            return "pt"

        pt_markers = [
            "voce", "voces", "resumo", "analise", "plano", "acao", "melhoria",
            "areas", "chamada", "cliente", "satisfacao", "sobre", "dados", "ligacao",
        ]
        es_markers = [
            "resumen", "analisis", "accion", "mejora", "cliente", "llamada", "datos",
        ]

        pt_score = sum(1 for marker in pt_markers if marker in text_norm)
        es_score = sum(1 for marker in es_markers if marker in text_norm)

        if pt_score >= 2:
            return "pt"
        if es_score >= 2:
            return "es"
        return "en"

    @staticmethod
    def _extract_first_user_message(request_body: dict) -> str:
        messages = request_body.get("messages", []) if isinstance(request_body, dict) else []
        for message in messages:
            if isinstance(message, dict) and message.get("role") == "user":
                return str(message.get("content") or "")
        return ""

    def _get_or_set_conversation_language(self, conversation_id: str, request_body: dict) -> str:
        if ChatService.language_cache is None:
            return "en"

        cached_language = ChatService.language_cache.get(conversation_id)
        if cached_language:
            return cached_language

        first_user_message = self._extract_first_user_message(request_body)
        detected = self._detect_language(first_user_message)
        ChatService.language_cache[conversation_id] = detected
        return detected

    @staticmethod
    def _build_language_enforced_query(user_query: str, language: str) -> str:
        # NOTE: Do NOT use "System requirement:" or similar prefixes here.
        # The agent's anti-injection instructions cause it to refuse any message
        # that appears to be injecting system-level rules.
        # Language handling is already covered by the agent's own instructions
        # ("Reply in the same language used by the user whenever possible").
        return user_query

    @staticmethod
    def _fallback_no_data_message(language: str) -> str:
        if language == "pt":
            return "Nao consegui responder com os dados atuais. Pode reformular sua pergunta com mais detalhes?"
        if language == "es":
            return "No pude responder con los datos actuales. Puedes reformular la pregunta con mas detalles?"
        return "I could not answer with the current data. Please rephrase your question with more details."

    def _get_memory_scope(self) -> str:
        if not self.memory_service:
            return ""

        user_details = get_authenticated_user_details(self.request.headers)
        user_principal_id = user_details.get("user_principal_id")
        tenant_id = get_tenantid(user_details.get("client_principal_b64"))
        return self.memory_service.build_scope(user_principal_id, tenant_id)

    @staticmethod
    def _build_memory_augmented_query(user_query: str, memory_context: str) -> str:
        if not memory_context:
            return user_query
        return f"{memory_context}\n\nCurrent user question:\n{user_query}"

    async def stream_openai_text(self, conversation_id: str, query: str, language: str = "en", guardrail_query: Optional[str] = None) -> StreamingResponse:
        """
        Get a streaming text response from OpenAI with enhanced guardrails.
        """
        # Guardrail Layer 1: Enhanced pre-query validation
        scope, reason = classify_query(guardrail_query if guardrail_query is not None else query)
        logger.debug(f"Query classification: {scope.value} - Reason: {reason}")
        
        if scope != QueryScope.IN_SCOPE:
            message = get_guardrail_message(scope)
            if message:
                logger.warning(f"Blocked query ({scope.value}): '{query[:100]}' - {reason}")
                yield message
                return
        
        thread = None
        complete_response = ""
        try:
            if not query:
                query = "Please provide a query."

            thread_id = None
            if ChatService.thread_cache is not None:
                thread_id = ChatService.thread_cache.get(conversation_id, None)
            agent_client = getattr(self.agent, "client", None)
            if thread_id and agent_client:
                thread = AzureAIAgentThread(client=agent_client, thread_id=thread_id)

            truncation_strategy = TruncationObject(type="last_messages", last_messages=4)

            async for response in self.agent.invoke_stream(messages=query, thread=thread, truncation_strategy=truncation_strategy):
                if ChatService.thread_cache is not None:
                    ChatService.thread_cache[conversation_id] = response.thread.id
                content = response.content
                if content is None:
                    continue
                complete_response += str(content)
                yield content

        except RuntimeError as e:
            complete_response = str(e)
            if "Rate limit is exceeded" in str(e):
                logger.error("Rate limit error: %s", e)
                raise AgentException(f"Rate limit is exceeded. {str(e)}") from e
            else:
                logger.error("RuntimeError: %s", e)
                raise AgentException(f"An unexpected runtime error occurred: {str(e)}") from e

        except Exception as e:
            complete_response = str(e)
            logger.error("Error in stream_openai_text: %s", e)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error streaming OpenAI text") from e

        finally:
            # Provide a fallback response when no data is received from OpenAI.
            if complete_response == "":
                logger.info("No response received from OpenAI.")
                thread_id = None
                if ChatService.thread_cache is not None:
                    thread_id = ChatService.thread_cache.pop(conversation_id, None)
                    if thread_id is not None:
                        corrupt_key = f"{conversation_id}_corrupt_{random.randint(1000, 9999)}"
                        ChatService.thread_cache[corrupt_key] = thread_id
                yield self._fallback_no_data_message(language)

    async def stream_chat_request(self, request_body, conversation_id, query):
        """
        Handles streaming chat requests.
        """
        history_metadata = request_body.get("history_metadata", {})
        session_language = self._get_or_set_conversation_language(conversation_id, request_body)
        memory_scope = self._get_memory_scope()

        scope, reason = classify_query(query or "")
        if scope != QueryScope.IN_SCOPE:
            message = get_guardrail_message(scope, session_language) or (
                "I can only answer questions grounded in call center knowledge data. "
                "Please ask about call transcripts, customer interactions, or call analytics."
            )
            logger.warning("Blocked query (%s): '%s' - %s", scope.value, (query or "")[:100], reason)

            async def blocked_generate():
                chat_completion_chunk = {
                    "id": str(uuid.uuid4()),
                    "model": "rag-model",
                    "created": int(time.time()),
                    "object": "extensions.chat.completion.chunk",
                    "choices": [
                        {
                            "messages": [{"role": "assistant", "content": message}],
                            "delta": {"role": "assistant", "content": message},
                        }
                    ],
                    "history_metadata": history_metadata,
                    "apim-request-id": "",
                }
                completion_chunk_obj = json.loads(
                    json.dumps(chat_completion_chunk),
                    object_hook=lambda d: SimpleNamespace(**d),
                )
                yield json.dumps(format_stream_response(completion_chunk_obj, history_metadata, "")) + "\n\n"

            return blocked_generate()

        async def generate():
            full_response_parts = []
            try:
                memory_context = ""
                if self.memory_service and memory_scope and query:
                    memory_context = await self.memory_service.search_context(memory_scope, query)

                enforced_query = self._build_language_enforced_query(query or "", session_language)
                enriched_query = self._build_memory_augmented_query(enforced_query, memory_context)
                async for chunk in self.stream_openai_text(
                    conversation_id,
                    enriched_query,
                    session_language,
                    guardrail_query=query or "",
                ):
                    if isinstance(chunk, dict):
                        chunk = json.dumps(chunk)  # Convert dict to JSON string

                    chunk_text = str(chunk)
                    if chunk_text:
                        full_response_parts.append(chunk_text)
                        chat_completion_chunk = {
                            "id": "",
                            "model": "",
                            "created": 0,
                            "object": "",
                            "choices": [
                                {
                                    "messages": [],
                                    "delta": {},
                                }
                            ],
                            "history_metadata": history_metadata,
                            "apim-request-id": "",
                        }

                        chat_completion_chunk["id"] = str(uuid.uuid4())
                        chat_completion_chunk["model"] = "rag-model"
                        chat_completion_chunk["created"] = int(time.time())
                        chat_completion_chunk["object"] = "extensions.chat.completion.chunk"
                        chat_completion_chunk["choices"][0]["messages"].append(
                            {"role": "assistant", "content": chunk_text}
                        )
                        chat_completion_chunk["choices"][0]["delta"] = {
                            "role": "assistant",
                            "content": chunk_text,
                        }

                        completion_chunk_obj = json.loads(
                            json.dumps(chat_completion_chunk),
                            object_hook=lambda d: SimpleNamespace(**d),
                        )
                        yield json.dumps(format_stream_response(completion_chunk_obj, history_metadata, "")) + "\n\n"

                full_response = "".join(full_response_parts).strip()
                if self.memory_service and memory_scope and query and full_response:
                    asyncio.create_task(
                        self.memory_service.update_from_turn(memory_scope, query, full_response)
                    )

            except AgentException as e:
                error_message = str(e)
                retry_after = "sometime"
                if "Rate limit is exceeded" in error_message:
                    match = re.search(r"Try again in (\d+) seconds", error_message)
                    if match:
                        retry_after = f"{match.group(1)} seconds"
                    logger.error("Rate limit error: %s", error_message)
                    yield json.dumps({"error": f"Rate limit is exceeded. Try again in {retry_after}."}) + "\n\n"
                else:
                    logger.error("AgentInvokeException: %s", error_message)
                    yield json.dumps({"error": "An error occurred. Please try again later."}) + "\n\n"

            except Exception as e:
                logger.error("Error in stream_chat_request: %s", e, exc_info=True)
                yield json.dumps({"error": "An error occurred while processing the request."}) + "\n\n"

        return generate()

    async def complete_chat_request(self, query, last_rag_response=None):
        """
        Completes a chat request by generating a chart from the RAG response.
        """
        if not last_rag_response:
            return {"error": "A previous RAG response is required to generate a chart."}

        # Process RAG response to generate chart data
        chart_data = await self.process_rag_response(last_rag_response, query)

        if not chart_data or "error" in chart_data:
            return {
                "error": "Chart could not be generated from this data. Please ask a different question.",
                "error_desc": str(chart_data),
            }

        logger.info("Successfully generated chart data.")
        return {
            "id": str(uuid.uuid4()),
            "model": "azure-openai",
            "created": int(time.time()),
            "object": chart_data,
        }
