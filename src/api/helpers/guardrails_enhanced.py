"""
Enhanced guardrails system with multiple layers of defense for call center knowledge mining.

Implements:
- Keyword-based filtering (fast pre-check)
- Intent-based classification (semantic filtering)
- Response validation (post-processing)
- Logging and monitoring
"""

import re
import unicodedata
import logging
from enum import Enum
from typing import Tuple, Dict, List

logger = logging.getLogger(__name__)

# Configuration: Define allowed topics and keywords
CALL_CENTER_KEYWORDS = {
    # Core call center metrics
    "call_metrics": ["call", "calls", "total calls", "number of calls", "call count", "call frequency", 
                     "call volume", "call duration", "handling time", "average handling time", "aht"],
    
    # Customer interaction
    "customer_interaction": ["customer", "client", "caller", "agent", "support", "service", "assistance", 
                            "contact", "interaction", "conversation", "communication"],
    
    # Analysis topics
    "analysis": ["analysis", "analyze", "insight", "insights", "summary", "summarize", "report", 
                "sentiment", "satisfaction", "feedback", "topic", "themes", "trends", "pattern"],
    
    # Call content
    "call_content": ["transcript", "transcripts", "conversation", "dialogue", "discussion", "chat", 
                    "message", "content", "speech", "audio", "recording"],
    
    # Billing & resolution
    "billing_resolution": ["billing", "billing issues", "charges", "payment", "account", "plan", 
                          "device", "connectivity", "resolution", "status", "resolved", "issue"],
    
    # Sentiment & satisfaction
    "sentiment_satisfaction": ["sentiment", "satisfaction", "satisfied", "dissatisfied", "happy", 
                              "unhappy", "positive", "negative", "neutral", "feedback", "complaint",
                              "praise", "issue", "problem", "challenge"],
}

# Blocked topics (explicitly forbidden)
BLOCKED_TOPICS = {
    "harmful": ["bomb", "violence", "hack", "malware", "exploit", "illegal"],
    "off_topic": ["recipe", "recipes", "poem", "story", "joke", "music", "sports", "politics", "religion",
                 "weather", "travel", "vacation", "movie", "game", "hobby"],
    "prompt_injection": ["prompt", "instruction", "system message", "rule", "guideline", "ignore", 
                        "override", "bypass", "jailbreak"],
}

# Allowed response contexts
ALLOWED_RESPONSE_CONTEXTS = {
    "data_analysis": ["data shows", "analysis reveals", "transcript indicates", "based on data"],
    "call_content": ["calls show", "conversations indicate", "transcripts reveal", "customer said"],
    "metrics": ["metric", "average", "total", "count", "percentage", "rate"],
}

class QueryScope(Enum):
    """Classification of query scope."""
    IN_SCOPE = "in_scope"
    OUT_OF_SCOPE = "out_of_scope"
    JAILBREAK_ATTEMPT = "jailbreak_attempt"
    BLOCKED = "blocked"


def normalize(text: str) -> str:
    """Normalize text for comparison."""
    return unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII').lower().strip()


def is_in_allowed_keywords(query: str, allowed_dict: Dict[str, List[str]]) -> Tuple[bool, str]:
    """
    Check if query contains keywords from allowed topics.
    
    Returns:
        Tuple[bool, str]: (is_match, category_matched)
    """
    query_norm = normalize(query)
    for category, keywords in allowed_dict.items():
        for keyword in keywords:
            # Use word boundary matching to avoid partial matches
            if re.search(rf"\b{re.escape(normalize(keyword))}\b", query_norm):
                return True, category
    return False, ""


def is_blocked_topic(query: str) -> bool:
    """
    Check if query contains explicitly blocked topics.
    
    Returns:
        bool: True if query contains blocked topic, False otherwise
    """
    query_norm = normalize(query)
    for category, keywords in BLOCKED_TOPICS.items():
        for keyword in keywords:
            keyword_norm = normalize(keyword)
            # Use word boundary check for more accurate matching
            pattern = r'\b' + re.escape(keyword_norm) + r'\b'
            if re.search(pattern, query_norm):
                logger.debug(f"Blocked topic '{keyword}' detected in '{query[:50]}'")
                return True
    return False


def check_jailbreak_attempt(query: str) -> bool:
    """
    Detect common jailbreak patterns.
    Also checks for attempts to manipulate agent behavior.
    """
    jailbreak_patterns = [
        # Prompt injection patterns
        r"(?:ignore|forget|override|bypass|disregard).*(?:previous|prior|instruction|rule|system|restriction|domain)",
        r"(?:pretend|assume|act\s+as\s+if).*(?:not|no)\s+(?:rule|guard|restriction)",
        r"(?:you\s+are|you're|act\s+as).*(?:different|new|unrestricted)",
        # Direct pretend pattern
        r"pretend\s+(?:to\s+be|you\s+are|i\s+want\s+you\s+to)",
        # Indirect manipulation
        r"(?:what\s+if|suppose|imagine).*(?:no|without).*(?:rule|guard|restriction)",
        # Role play manipulation
        r"(?:can\s+you\s+help\s+me\s+with).*(?:ignore|override|bypass)",
        # Dan and similar
        r"(?:dan|do\s+anything\s+now)",
    ]
    
    query_norm = normalize(query)
    for pattern in jailbreak_patterns:
        if re.search(pattern, query_norm):
            logger.warning(f"Potential jailbreak attempt detected: {query[:100]}")
            return True
    return False


def classify_query(query: str) -> Tuple[QueryScope, str]:
    """
    Classify the scope of a query using multiple checks.
    
    Returns:
        Tuple[QueryScope, str]: (scope, reason)
    """
    if not query or not query.strip():
        return QueryScope.OUT_OF_SCOPE, "Empty query"
    
    # Check 1: Jailbreak detection
    if check_jailbreak_attempt(query):
        return QueryScope.JAILBREAK_ATTEMPT, "Jailbreak pattern detected"
    
    # Check 2: Blocked topics
    if is_blocked_topic(query):
        return QueryScope.BLOCKED, "Blocked topic detected"
    
    # Check 3: Allowed keywords
    is_allowed, category = is_in_allowed_keywords(query, CALL_CENTER_KEYWORDS)
    if is_allowed:
        return QueryScope.IN_SCOPE, f"Call center topic: {category}"
    
    # Check 4: Conversational follow-ups (allowed with context history)
    # Generic conversational phrases that need prior context
    conversational_phrases = ["yes", "no", "tell me more", "explain", "continue", "next", "previous"]
    if normalize(query) in conversational_phrases:
        # In practice, this would be allowed if there's conversation history
        return QueryScope.IN_SCOPE, "Conversational follow-up"
    
    return QueryScope.OUT_OF_SCOPE, "Does not match call center domain"


def validate_response(response: str, original_query: str) -> Tuple[bool, str]:
    """
    Validate response doesn't contain out-of-scope content.
    Post-processing guardrail.
    
    Returns:
        Tuple[bool, str]: (is_valid, reason)
    """
    response_norm = normalize(response)
    
    # Check if response contains recipe, code, or other non-call-center content
    forbidden_response_phrases = [
        r"here['`]s\s+a\s+(?:recipe|poem|story|joke|code|tutorial|guide)",
        r"(?:def |class |function |async )\w+\(",  # Code patterns
        r"(?:ingredients|instructions:|mix|blend|bake)",  # Recipe patterns
    ]
    
    for pattern in forbidden_response_phrases:
        if re.search(pattern, response_norm):
            logger.warning(f"Post-response validation failed: forbidden content detected")
            return False, "Response contains non-call-center content"
    
    return True, "Response valid"


def is_in_scope(query: str) -> bool:
    """
    Main guardrail function - backward compatible with existing code.
    
    Returns:
        bool: True if query is in scope, False otherwise
    """
    scope, reason = classify_query(query)
    logger.debug(f"Query classification: {scope.value} - {reason}")
    return scope == QueryScope.IN_SCOPE


def get_scope_reason(query: str) -> Tuple[QueryScope, str]:
    """
    Get detailed scope classification with reason.
    Useful for logging and debugging.
    """
    return classify_query(query)


def get_guardrail_message(scope: QueryScope) -> str:
    """Get appropriate message based on query scope."""
    messages = {
        QueryScope.IN_SCOPE: None,  # No message for in-scope queries
        QueryScope.OUT_OF_SCOPE: "I am only allowed to answer questions about call center operations, customer interactions, and call analytics. Please ask something related to call transcripts, customer satisfaction, call metrics, or billing/resolution topics.",
        QueryScope.BLOCKED: "This topic is not allowed. I can only assist with call center knowledge mining and customer service analytics.",
        QueryScope.JAILBREAK_ATTEMPT: "I cannot process that request. Please ask questions directly related to call center operations and customer service analytics.",
    }
    return messages.get(scope)
