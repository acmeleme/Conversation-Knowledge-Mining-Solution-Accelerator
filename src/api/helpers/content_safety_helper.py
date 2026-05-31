"""
content_safety_helper.py — Phase 4: Azure AI Content Safety integration helper.

This module provides helper functions for building and evaluating Content Safety
API payloads. The actual API call is made by APIM (via send-request policy),
but these helpers are used for local validation and testing.
"""

import os
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

CONTENT_SAFETY_CATEGORIES = ["Hate", "Violence", "Sexual", "SelfHarm"]
CONTENT_SAFETY_BLOCK_THRESHOLD = 4  # Block severity >= 4


def build_content_safety_payload(text: str, max_length: int = 5000) -> dict[str, Any]:
    """Build the request payload for Azure AI Content Safety text analysis."""
    text = text or ""
    if len(text) > max_length:
        text = text[:max_length]
    return {
        "text": text if text else "empty",
        "categories": CONTENT_SAFETY_CATEGORIES,
        "outputType": "FourSeverityLevels",
    }


def evaluate_content_safety_response(response_body: Optional[dict[str, Any]]) -> str:
    """
    Evaluate a Content Safety API response and return a result string.

    Returns:
        - "SAFE" if all categories are below threshold
        - "BLOCKED:{category}" if any category meets/exceeds threshold
        - "UNAVAILABLE" if response is empty or malformed
    """
    if not response_body:
        return "UNAVAILABLE"

    categories = response_body.get("categoriesAnalysis")
    if categories is None:
        return "SAFE"
    if not isinstance(categories, list):
        return "UNAVAILABLE"

    for cat in categories:
        if not isinstance(cat, Mapping):
            return "UNAVAILABLE"
        severity = cat.get("severity", 0) or 0
        if severity >= CONTENT_SAFETY_BLOCK_THRESHOLD:
            return f"BLOCKED:{cat.get('category', 'Unknown')}"

    return "SAFE"


def extract_user_message(messages: Optional[list[dict[str, Any]]]) -> str:
    """Extract the last user message from a chat messages array."""
    if not messages:
        return ""
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "user":
            content = msg.get("content", "")
            return content if isinstance(content, str) else ""
    return ""


def build_audit_log_entry(
    user_id: Optional[str],
    request_id: str,
    content_safety_result: str,
    endpoint: str,
) -> dict[str, str]:
    """Build an audit log entry for LGPD/ISO 27001 compliance."""
    return {
        "user_id": user_id or "anonymous",
        "request_id": request_id,
        "content_safety_result": content_safety_result,
        "endpoint": endpoint,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": "4.0",
    }


def resolve_apim_subscription_key(
    env: Optional[Mapping[str, str]] = None,
    key_vault_client: Any = None,
    secret_name: str = "APIM_SUBSCRIPTION_KEY",
) -> Optional[str]:
    """Resolve the APIM subscription key, preferring environment variables."""
    env = env or os.environ
    env_value = env.get("APIM_SUBSCRIPTION_KEY")
    if env_value:
        return env_value

    if key_vault_client is None:
        return None

    try:
        secret = key_vault_client.get_secret(secret_name)
    except Exception:
        return None

    if isinstance(secret, str):
        return secret

    return getattr(secret, "value", None)
