"""
Enhanced ChatService with multi-layer guardrails enforcement.
Implements guardrails at query pre-check, agent instructions, and response validation stages.
"""

import json
import logging
from fastapi import HTTPException, Request, status
from fastapi.responses import StreamingResponse

from helpers.guardrails_enhanced import (
    classify_query, QueryScope, get_guardrail_message, validate_response
)
from helpers.guardrails_config import GuardrailsConfig
from semantic_kernel.agents import AzureAIAgentThread
from semantic_kernel.exceptions.agent_exceptions import AgentException
from azure.ai.agents.models import TruncationObject
from cachetools import TTLCache
from helpers.utils import format_stream_response
from common.config.config import Config
import asyncio
import random

# Constants
HOST_NAME = "CKM"
HOST_INSTRUCTIONS = "Answer questions about call center operations"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GuardrailViolation(Exception):
    """Raised when guardrail is violated."""
    pass


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
                    print(f"Thread deleted: {thread_id}")
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


class ChatServiceEnhanced:
    """
    Enhanced service for handling chat interactions with multi-layer guardrails.
    
    Implements guardrails at three levels:
    1. Pre-query validation (before sending to agent)
    2. Agent instructions (system prompt level)
    3. Post-response validation (after receiving response)
    """

    thread_cache = None

    def __init__(self, request: Request):
        config = Config()
        guardrail_config = GuardrailsConfig()
        
        self.azure_openai_deployment_name = config.azure_openai_deployment_model
        self.agent = request.app.state.agent
        self.guardrail_config = guardrail_config

        if ChatServiceEnhanced.thread_cache is None:
            ChatServiceEnhanced.thread_cache = ExpCache(maxsize=1000, ttl=3600.0, agent=self.agent)

    async def stream_openai_text(self, conversation_id: str, query: str) -> StreamingResponse:
        """
        Get a streaming text response from OpenAI with multi-layer guardrail enforcement.
        
        Args:
            conversation_id: Unique conversation identifier
            query: User query string
            
        Yields:
            Streamed response content or guardrail violation message
            
        Raises:
            GuardrailViolation: If strict mode is enabled and query violates guardrails
        """
        thread = None
        complete_response = ""
        
        try:
            if not query:
                query = "Please provide a query."
            
            # ========== LAYER 1: PRE-QUERY VALIDATION ==========
            if self.guardrail_config.ENABLE_PRE_QUERY_CHECK:
                scope, reason = classify_query(query)
                
                # Log classification details
                if self.guardrail_config.LOG_QUERY_CLASSIFICATION:
                    logger.info(f"Query classification: {scope.value} - '{query[:100]}' - Reason: {reason}")
                
                # Handle violations
                if scope != QueryScope.IN_SCOPE:
                    if self.guardrail_config.LOG_BLOCKED_QUERIES:
                        logger.warning(f"Blocked query ({scope.value}): '{query[:100]}' - {reason}")
                    
                    # Check for jailbreak attempts
                    if scope == QueryScope.JAILBREAK_ATTEMPT and self.guardrail_config.ALERT_ON_JAILBREAK:
                        if self.guardrail_config.STRICT_MODE:
                            raise GuardrailViolation(f"Jailbreak attempt detected: {reason}")
                        else:
                            logger.error(f"Jailbreak attempt detected: {reason}")
                    
                    # Return appropriate guardrail message
                    message = get_guardrail_message(scope)
                    if message:
                        yield message
                        return

            # ========== LAYER 2: AGENT INSTRUCTIONS (System Prompt) ==========
            # The agent instructions already contain guardrails (set in ConversationAgentFactoryEnhanced)
            # This is the second layer of defense

            # ========== PROCEED WITH AGENT INVOCATION ==========
            thread_id = None
            if ChatServiceEnhanced.thread_cache is not None:
                thread_id = ChatServiceEnhanced.thread_cache.get(conversation_id, None)
            
            if thread_id:
                thread = AzureAIAgentThread(client=self.agent.client, thread_id=thread_id)

            truncation_strategy = TruncationObject(type="last_messages", last_messages=4)

            async for response in self.agent.invoke_stream(
                messages=query, 
                thread=thread, 
                truncation_strategy=truncation_strategy
            ):
                if ChatServiceEnhanced.thread_cache is not None:
                    ChatServiceEnhanced.thread_cache[conversation_id] = response.thread.id
                
                response_content = str(response.content)
                
                # ========== LAYER 3: POST-RESPONSE VALIDATION ==========
                if self.guardrail_config.ENABLE_POST_RESPONSE_CHECK:
                    is_valid, validation_reason = validate_response(response_content, query)
                    
                    if not is_valid:
                        logger.warning(f"Post-response validation failed: {validation_reason}")
                        if self.guardrail_config.LOG_BLOCKED_QUERIES:
                            logger.warning(f"Blocked response: '{response_content[:100]}' - {validation_reason}")
                        
                        if self.guardrail_config.STRICT_MODE:
                            raise GuardrailViolation(f"Response validation failed: {validation_reason}")
                
                complete_response += response_content
                yield response_content

        except GuardrailViolation as e:
            complete_response = str(e)
            logger.error(f"Guardrail violation: {e}")
            if self.guardrail_config.STRICT_MODE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Request violates content policy"
                ) from e
            else:
                yield "Your request cannot be processed. Please ensure your question is related to call center operations."
                
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
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error streaming OpenAI text"
            ) from e

        finally:
            # Provide a fallback response when no data is received from OpenAI
            if complete_response == "":
                logger.info("No response received from OpenAI.")
                thread_id = None
                if ChatServiceEnhanced.thread_cache is not None:
                    thread_id = ChatServiceEnhanced.thread_cache.pop(conversation_id, None)
                    if thread_id is not None:
                        corrupt_key = f"{conversation_id}_corrupt_{random.randint(1000, 9999)}"
                        ChatServiceEnhanced.thread_cache[corrupt_key] = thread_id
                yield "I cannot answer this question with the current data. Please rephrase or add more details."

    async def stream_chat_request(self, request_body, conversation_id, query):
        """
        Handles streaming chat requests with guardrail enforcement.
        """
        # Layer 1: Pre-query check
        if self.guardrail_config.ENABLE_PRE_QUERY_CHECK:
            scope, reason = classify_query(query)
            if scope != QueryScope.IN_SCOPE:
                message = get_guardrail_message(scope)
                if message:
                    return StreamingResponse(
                        self._error_generator(message),
                        media_type="text/event-stream"
                    )
        
        return StreamingResponse(
            self.stream_openai_text(conversation_id, query),
            media_type="text/event-stream"
        )

    async def _error_generator(self, message: str):
        """Generate error response as streaming output."""
        yield message
