"""Azure AI Foundry Memory Store integration helpers."""

import asyncio
import logging
import re
from typing import Optional

try:
    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import MemorySearchOptions
    MEMORY_SDK_AVAILABLE = True
except ImportError:
    AIProjectClient = None
    MemorySearchOptions = None
    MEMORY_SDK_AVAILABLE = False

from common.config.config import Config
from helpers.azure_credential_utils import get_azure_credential

logger = logging.getLogger(__name__)

_SCOPE_SANITIZE_RE = re.compile(r"[^A-Za-z0-9_-]")
_MAX_SCOPE_LENGTH = 256


class FoundryMemoryService:
    """Service wrapper around Azure AI Foundry Memory Store operations."""

    def __init__(self):
        self.config = Config()
        self.enabled = bool(
            MEMORY_SDK_AVAILABLE
            and self.config.azure_ai_memory_enabled
            and self.config.azure_ai_memory_store_name
            and self.config.ai_project_endpoint
        )
        self.memory_store_name = self.config.azure_ai_memory_store_name
        self.update_delay_seconds = self.config.azure_ai_memory_update_delay_seconds
        self.project_client = None
        self._previous_search_ids: dict[str, str] = {}
        self._previous_update_ids: dict[str, str] = {}

        if not MEMORY_SDK_AVAILABLE:
            logger.error("Azure AI Projects memory SDK surface is unavailable; Foundry memory integration is disabled.")
            return

        if not self.enabled:
            return

        try:
            client_kwargs = {
                "endpoint": self.config.ai_project_endpoint,
                "credential": get_azure_credential(client_id=self.config.azure_client_id),
                "api_version": self.config.ai_project_api_version,
            }
            try:
                self.project_client = AIProjectClient(allow_preview=True, **client_kwargs)
            except TypeError:
                self.project_client = AIProjectClient(**client_kwargs)
        except Exception:
            logger.error("Failed to initialize FoundryMemoryService", exc_info=True)
            self.enabled = False
            self.project_client = None

    @staticmethod
    def build_scope(user_principal_id: Optional[str], tenant_id: Optional[str]) -> str:
        """Build a stable memory scope for the authenticated user."""
        normalized_user = _SCOPE_SANITIZE_RE.sub("_", (user_principal_id or "").strip())
        normalized_tenant = _SCOPE_SANITIZE_RE.sub("_", (tenant_id or "").strip())

        if not normalized_user:
            return ""

        parts = []
        if normalized_tenant:
            parts.append(f"tenant_{normalized_tenant}")
        parts.append(f"user_{normalized_user}")
        return "__".join(parts)[:_MAX_SCOPE_LENGTH]

    async def search_context(self, scope: str, query: str) -> str:
        """Retrieve relevant memories and format them as prompt context."""
        if not self.enabled or not self.project_client or not scope or not query:
            return ""

        def _search():
            previous_search_id = self._previous_search_ids.get(scope)
            return self.project_client.beta.memory_stores.search_memories(
                name=self.memory_store_name,
                scope=scope,
                items=query,
                previous_search_id=previous_search_id,
                options=MemorySearchOptions(max_memories=5),
            )

        try:
            search_response = await asyncio.to_thread(_search)
            search_id = getattr(search_response, "search_id", None)
            if search_id:
                self._previous_search_ids[scope] = search_id

            memories = getattr(search_response, "memories", []) or []
            formatted_memories = []
            for memory in memories:
                memory_item = getattr(memory, "memory_item", None)
                content = getattr(memory_item, "content", None)
                if content:
                    formatted_memories.append(f"- {content}")

            if not formatted_memories:
                return ""

            return "Relevant prior user memories:\n" + "\n".join(formatted_memories)
        except Exception:
            logger.error("Failed to search Foundry memories for scope %s", scope, exc_info=True)
            return ""

    async def update_from_turn(self, scope: str, user_text: str, assistant_text: str) -> None:
        """Submit the current conversation turn to the memory store."""
        if not self.enabled or not self.project_client or not scope or not user_text or not assistant_text:
            return

        items = [
            {"role": "user", "type": "message", "content": user_text},
            {"role": "assistant", "type": "message", "content": assistant_text},
        ]

        def _update():
            previous_update_id = self._previous_update_ids.get(scope)
            return self.project_client.beta.memory_stores.begin_update_memories(
                name=self.memory_store_name,
                scope=scope,
                items=items,
                previous_update_id=previous_update_id,
                update_delay=self.update_delay_seconds,
            )

        try:
            update_poller = await asyncio.to_thread(_update)
            update_id = getattr(update_poller, "update_id", None)
            if update_id:
                self._previous_update_ids[scope] = update_id
        except Exception:
            logger.error("Failed to update Foundry memories for scope %s", scope, exc_info=True)
