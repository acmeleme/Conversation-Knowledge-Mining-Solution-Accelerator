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
                            "contact", "interaction", "conversation", "communication", "cliente", "clientes",
                            "atendente", "atendimento", "chamado", "chamados", "servico", "servico"],
    
    # Analysis topics
    "analysis": ["analysis", "analyze", "insight", "insights", "summary", "summarize", "report", 
                "sentiment", "satisfaction", "feedback", "topic", "themes", "trends", "pattern",
                "resumo", "resumir", "analise", "analise", "relatorio", "relatorio",
                "plano de acao", "plano de acao", "acoes", "acoes", "melhoria", "areas envolvidas", "areas envolvidas"],
    
    # Call content
    "call_content": ["transcript", "transcripts", "conversation", "dialogue", "discussion", "chat", 
                    "message", "content", "speech", "audio", "recording", "transcricao", "transcricao",
                    "ligacao", "ligacao", "ligacoes", "ligacoes"],
    
    # Billing & resolution
    "billing_resolution": ["billing", "billing issues", "charges", "payment", "account", "plan", 
                          "device", "connectivity", "resolution", "status", "resolved", "issue",
                          "conta", "cobranca", "cobranca", "pagamento", "resolucao", "resolucao"],
    
    # Sentiment & satisfaction
    "sentiment_satisfaction": ["sentiment", "satisfaction", "satisfied", "dissatisfied", "happy", 
                              "unhappy", "positive", "negative", "neutral", "feedback", "complaint",
                              "praise", "issue", "problem", "challenge", "sentimento", "satisfacao",
                              "insatisfeito", "insatisfeita", "frustrado", "frustrada"],

    # Known call-center topic names commonly used in this solution demo
    "known_topics": [
        "account information updates",
        "service activation",
        "billing and payment issues",
        "device troubleshooting",
        "parental controls",
        "internet services",
        "international roaming",
        "loyalty programs",
        "plan management",
        "network connectivity",
        "appointment scheduling",
        "customer feedback",
    ],
}

# Blocked topics (explicitly forbidden)
BLOCKED_TOPICS = {
    "harmful": ["bomb", "violence", "hack", "malware", "exploit", "illegal", "fraud"],
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
        r"act\s+as\s+if\s+i'?m\s+your\s+developer",
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

    # Check 4: Analysis-intent + known-topic heuristic for multilingual requests.
    # Example: "crie um resumo sobre Account Information Updates..."
    query_norm = normalize(query)
    analysis_intent_terms = [
        "summary", "summarize", "analysis", "analyze", "action plan", "next steps",
        "resumo", "resumir", "analise", "plano de acao", "acoes", "melhoria",
    ]
    known_topics = CALL_CENTER_KEYWORDS.get("known_topics", [])
    if any(term in query_norm for term in analysis_intent_terms) and any(
        normalize(topic) in query_norm for topic in known_topics
    ):
        return QueryScope.IN_SCOPE, "Analysis request over known call-center topic"
    
    # Check 5: Conversational follow-ups and contextual planning requests.
    # These are common after an in-scope response and should not be blocked.
    conversational_phrases = [
        "yes", "no", "tell me more", "explain", "continue", "next", "previous",
        "ok", "okay", "go on", "based on the previous summary", "based on the summary",
        "de acordo com o resumo", "de acordo com o resumo anterior", "com base no resumo",
        "com base no resumo anterior", "plano de acao", "plano de ação", "next steps",
        "action plan", "areas envolvidas", "areas envolvidas e acao", "ação de cada área",
    ]
    off_topic_hints = [
        "joke", "poem", "recipe", "travel", "movie", "music", "weather", "sports",
        "receita", "piada", "filme", "musica", "clima",
    ]
    if any(phrase in query_norm for phrase in conversational_phrases) and not any(
        hint in query_norm for hint in off_topic_hints
    ):
        return QueryScope.IN_SCOPE, "Conversational/contextual follow-up"
    
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


def get_guardrail_message(scope: QueryScope, language: str = "en") -> str:
    """Get appropriate message based on query scope and preferred language."""
    language_key = (language or "en").lower()

    messages_en = {
        QueryScope.IN_SCOPE: None,
        QueryScope.OUT_OF_SCOPE: "Sorry, I can only help with call center operations, customer interactions, and call analytics. This request is not allowed outside that scope. If you want, I can help rewrite your request to focus on transcripts, sentiment, call metrics, billing, or resolution topics.",
        QueryScope.BLOCKED: "I am sorry, but this topic is not allowed. I can gladly help with call center knowledge mining and customer service analytics.",
        QueryScope.JAILBREAK_ATTEMPT: "I cannot process that request. Please send a direct question related to call center operations or customer service analytics.",
    }

    messages_pt = {
        QueryScope.IN_SCOPE: None,
        QueryScope.OUT_OF_SCOPE: "Desculpe, eu so posso ajudar com operacoes de call center, interacoes com clientes e analises de chamadas. Se quiser, eu posso reformular sua pergunta para focar em transcricoes, sentimento, metricas de chamada, cobranca ou resolucao.",
        QueryScope.BLOCKED: "Desculpe, nao posso ajudar com esse tema. Posso ajudar com analise de call center e atendimento ao cliente.",
        QueryScope.JAILBREAK_ATTEMPT: "Nao posso processar esse pedido. Por favor, envie uma pergunta direta relacionada a operacoes de call center ou analise de atendimento.",
    }

    messages_es = {
        QueryScope.IN_SCOPE: None,
        QueryScope.OUT_OF_SCOPE: "Lo siento, solo puedo ayudar con operaciones de call center, interacciones con clientes y analitica de llamadas. Si quieres, puedo ayudarte a reformular la solicitud para enfocarla en transcripciones, sentimiento, metricas de llamadas, facturacion o resolucion.",
        QueryScope.BLOCKED: "Lo siento, no puedo ayudar con ese tema. Puedo ayudarte con analitica de call center y atencion al cliente.",
        QueryScope.JAILBREAK_ATTEMPT: "No puedo procesar esa solicitud. Envia una pregunta directa relacionada con operaciones de call center o analitica de servicio al cliente.",
    }

    if language_key.startswith("pt"):
        return messages_pt.get(scope)
    if language_key.startswith("es"):
        return messages_es.get(scope)
    return messages_en.get(scope)
