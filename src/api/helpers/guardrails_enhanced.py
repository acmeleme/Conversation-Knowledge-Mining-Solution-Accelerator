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
                     "call volume", "call duration", "handling time", "average handling time", "aht",
                     "chamada", "chamadas", "total de chamadas", "numero de chamadas", "volume de chamadas",
                     "duracao", "tempo de atendimento", "tma", "tempo medio"],
    
    # Customer interaction
    "customer_interaction": ["customer", "client", "caller", "agent", "support", "service", "assistance", 
                           "contact", "interaction", "conversation", "communication", "cliente", "clientes",
                           "atendente", "atendimento", "chamado", "chamados", "servico", "servicos",
                           "operador", "operadores", "reclamacao", "reclamacoes", "elogio", "elogios",
                           "satisfacao", "insatisfacao", "feedback", "suporte"],
    
    # Analysis topics
    "analysis": ["analysis", "analyze", "insight", "insights", "summary", "summarize", "report", 
                "sentiment", "satisfaction", "feedback", "topic", "themes", "trends", "pattern",
                "resumo", "resumir", "analise", "analises", "relatorio", "relatorios",
                "plano de acao", "plano de ações", "acoes", "acoes de melhoria", "melhoria",
                "areas envolvidas", "tendencia", "tendencias", "padrao", "padroes", "destaque"],
    
    # Call content
    "call_content": ["transcript", "transcripts", "conversation", "dialogue", "discussion", "chat", 
                    "message", "content", "speech", "audio", "recording", "transcricao", "transcricoes",
                    "ligacao", "ligacoes", "conversa", "conversas", "historico", "interacao"],
    
    # Financial domain — FinanceiraX S.A. products
    "financial_products": [
        "seguro", "seguros", "apolice", "apolices", "sinistro", "sinistros", "indenizacao",
        "premio", "cobertura", "franquia", "vistoria", "beneficiario", "contratacao de seguro",
        "cancelamento de seguro",
        "cartao", "cartao de credito", "cartoes", "fatura", "faturas", "limite", "limite do cartao",
        "bloqueio", "desbloqueio", "contestacao", "anuidade", "pontos", "cashback", "bandeira",
        "segunda via", "segunda via do cartao",
        "emprestimo", "emprestimos", "parcela", "parcelas", "juros", "taxa de juros", "cet",
        "amortizacao", "quitacao", "renegociacao", "inadimplencia", "atraso", "refinanciamento",
        "credito", "credito especial", "credito consignado", "consignado", "margem", "margem consignavel",
        "portabilidade", "portabilidade de credito", "desconto em folha", "inss", "contrato",
        "consorcio", "consorcios", "carta de credito", "lance", "contemplacao", "cota", "cotas",
        "assembleia", "grupo", "transferencia de cota",
        "cobranca", "cobrancas", "pagamento", "pagamentos", "debito", "creditar", "financeiro",
        "financeira", "financeirax",
    ],
    
    # Sentiment & satisfaction
    "sentiment_satisfaction": ["sentiment", "satisfaction", "satisfied", "dissatisfied", "happy", 
                             "unhappy", "positive", "negative", "neutral", "feedback", "complaint",
                             "praise", "issue", "problem", "challenge", "sentimento", "satisfacao",
                             "insatisfeito", "insatisfeita", "frustrado", "frustrada",
                             "positivo", "negativo", "neutro", "reclamacao", "elogio"],

    # Data visualization & charts
    "data_visualization": [
        "chart", "charts", "graph", "graphs", "plot", "visualization", "visualize",
        "bar chart", "pie chart", "line chart", "doughnut", "histogram",
        "grafico", "graficos", "grafico de barras", "grafico de pizza",
        "grafico de linhas", "grafico de rosca", "visualizacao", "visualizar",
        "crie um grafico", "criar grafico", "gerar grafico", "montar grafico",
        "mostrar grafico", "exibir grafico", "plotar",
    ],

    # Known call-center topic names — must match the actual topic names in the SQL database.
    # These ensure that queries like "resumo sobre Seguro" or "analise de Cartao de Credito"
    # are always classified as IN_SCOPE even without other call-center keywords.
    "known_topics": [
        # Tópicos reais da tabela processed_data do sqldb-financeirax01
        "Seguro — Contratacao e Cancelamento",
        "Seguro — Sinistros e Indenizacoes",
        "Cartao de Credito — Fatura e Pagamento",
        "Cartao de Credito — Bloqueio e Contestacao",
        "Emprestimos — Simulacao e Contratacao",
        "Emprestimos — Renegociacao e Inadimplencia",
        "Credito Especial — Credito Consignado",
        "Credito Especial — Portabilidade de Credito",
        "Consorcio — Carta de Credito e Contemplacao",
        "Consorcio — Duvidas sobre Grupo e Cota",
        # Nomes simplificados para reconhecimento flexível
        "seguro contratacao",
        "seguro cancelamento",
        "seguro sinistro",
        "seguro indenizacao",
        "cartao fatura",
        "cartao pagamento",
        "cartao bloqueio",
        "cartao contestacao",
        "emprestimo simulacao",
        "emprestimo contratacao",
        "emprestimo renegociacao",
        "emprestimo inadimplencia",
        "credito consignado",
        "credito especial",
        "portabilidade credito",
        "consorcio carta de credito",
        "consorcio contemplacao",
        "consorcio grupo",
        "consorcio cota",
    ],
}

# Blocked topics (explicitly forbidden)
BLOCKED_TOPICS = {
    "harmful": ["bomb", "violence", "hack", "malware", "exploit", "illegal", "fraud",
                "bomba", "violencia", "hackear", "fraude", "ilegal"],
    # Only block clear jailbreak keywords — contextual patterns (ignore+instruction, etc.)
    # are handled more precisely by check_jailbreak_attempt() with multi-token regex.
    # Single common words like "rule", "prompt", "ignore", "guideline" are too broad
    # and would block legitimate call-center queries.
    "prompt_injection": ["jailbreak", "bypass", "override"],
}

# Allowed response contexts
ALLOWED_RESPONSE_CONTEXTS = {
    "data_analysis": ["data shows", "analysis reveals", "transcript indicates", "based on data",
                      "dados mostram", "analise revela", "transcricao indica", "com base nos dados"],
    "call_content": ["calls show", "conversations indicate", "transcripts reveal", "customer said",
                     "chamadas mostram", "conversas indicam", "transcricoes revelam", "cliente disse"],
    "metrics": ["metric", "average", "total", "count", "percentage", "rate",
                "metrica", "media", "total", "contagem", "percentual", "taxa"],
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
        # Prompt injection patterns (EN)
        r"(?:ignore|forget|override|bypass|disregard).*(?:previous|prior|instruction|rule|system|restriction|domain)",
        r"(?:pretend|assume|act\s+as\s+if).*(?:not|no)\s+(?:rule|guard|restriction)",
        r"act\s+as\s+if\s+i'?m\s+your\s+developer",
        r"(?:you\s+are|you're|act\s+as).*(?:different|new|unrestricted)",
        r"pretend\s+(?:to\s+be|you\s+are|i\s+want\s+you\s+to)",
        r"(?:what\s+if|suppose|imagine).*(?:no|without).*(?:rule|guard|restriction)",
        r"(?:can\s+you\s+help\s+me\s+with).*(?:ignore|override|bypass)",
        r"(?:dan|do\s+anything\s+now)",
        # Prompt injection patterns (PT-BR)
        r"(?:ignore|esqueca|desconsidere|ignora).*(?:instrucao|regra|sistema|restricao|anterior)",
        r"(?:finja|simule|aja\s+como).*(?:sem|nao\s+tem).*(?:regra|restricao|limite)",
        r"(?:voce\s+e|vc\s+e|se\s+comporte\s+como).*(?:diferente|novo|sem\s+restricao|livre)",
        r"ignore\s+(?:todas|suas)\s+(?:instrucoes|regras)",
        r"(?:esquece|ignora)\s+(?:o\s+que\s+te|suas)\s+(?:disseram|instrucoes)",
        r"prompt\s+(?:injection|inject|hack)",
        r"mostre\s+(?:seu\s+)?(?:prompt|instrucao|system\s+prompt)",
        r"revele\s+(?:suas\s+)?(?:instrucoes|regras|prompt)",
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
    # Example: "crie um resumo sobre Seguro — Sinistros e Indenizacoes..."
    query_norm = normalize(query)
    analysis_intent_terms = [
        "summary", "summarize", "analysis", "analyze", "action plan", "next steps",
        "resumo", "resumir", "analise", "plano de acao", "acoes", "melhoria",
        "relatorio", "insights", "tendencia", "comparar", "comparativo",
        "chart", "graph", "plot", "visualization", "visualize",
        "grafico", "graficos", "visualizacao", "visualizar", "plotar",
        "crie um grafico", "criar grafico", "gerar grafico",
    ]
    known_topics = CALL_CENTER_KEYWORDS.get("known_topics", [])
    if any(term in query_norm for term in analysis_intent_terms) and any(
        normalize(topic) in query_norm for topic in known_topics
    ):
        return QueryScope.IN_SCOPE, "Analysis request over known call-center topic"
    
    # Check 5: Conversational follow-ups and contextual planning requests.
    # These are common after an in-scope response and should not be blocked.
    conversational_phrases = [
        # Greetings (English/Portuguese/Spanish)
        "hello", "hi", "hey", "good morning", "good afternoon", "good evening",
        "ola", "oi", "bom dia", "boa tarde", "boa noite",
        "hola", "buenos dias", "buenas tardes", "buenas noches",
        # Follow-ups
        "yes", "no", "tell me more", "explain", "continue", "next", "previous",
        "ok", "okay", "go on", "based on the previous summary", "based on the summary",
        "de acordo com o resumo", "de acordo com o resumo anterior", "com base no resumo",
        "com base no resumo anterior", "plano de acao", "plano de acao", "next steps",
        "action plan", "areas envolvidas", "areas envolvidas e acao", "acao de cada area",
        "obrigado", "obrigada", "por favor", "pode explicar", "pode detalhar",
        # Capability/help intents (must stay in-scope to avoid false refusals)
        "quais perguntas pode responder", "quais perguntas voce pode responder",
        "o que voce pode responder", "o que vc pode responder",
        "como pode me ajudar", "como voce pode me ajudar", "como vc pode me ajudar",
        "como pode ajudar", "como voce pode ajudar", "como vc pode ajudar",
        "o que voce faz", "o que vc faz", "como funciona",
        "what can you answer", "what can you do", "how can you help me",
    ]
    off_topic_hints = [
        "joke", "poem", "recipe", "travel", "movie", "music", "weather", "sports",
        "receita", "piada", "filme", "musica", "clima", "previsao do tempo",
        "esporte", "futebol", "viagem", "poema", "conto", "historia ficticia",
        "bake", "cake", "chocolate", "cooking", "baker", "dessert", "pastry",
        "machine learning", "deep learning", "neural network", "artificial intelligence",
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


def get_guardrail_message(scope: QueryScope, language: str = "pt") -> str:
    """Get appropriate message based on query scope and preferred language."""
    language_key = (language or "pt").lower()

    messages_en = {
        QueryScope.IN_SCOPE: None,
        QueryScope.OUT_OF_SCOPE: (
            "Sorry, I can only help with call center operations, customer interactions, "
            "and call analytics for FinanceiraX S.A. This request is outside my scope. "
            "I can help with topics such as: insurance, credit cards, loans, special credit, "
            "or consortiums. How can I help you with one of these topics?"
        ),
        QueryScope.BLOCKED: (
            "I am sorry, but this topic is not allowed. I can gladly help with "
            "call center knowledge mining and customer service analytics for FinanceiraX S.A."
        ),
        QueryScope.JAILBREAK_ATTEMPT: (
            "I cannot process that request. My guidelines are fixed and cannot be changed. "
            "Please send a direct question related to call center operations or customer "
            "service analytics for FinanceiraX S.A."
        ),
    }

    messages_pt = {
        QueryScope.IN_SCOPE: None,
        QueryScope.OUT_OF_SCOPE: (
            "Desculpe, esse assunto está fora do meu escopo de atuação. Sou especialista em "
            "análise de atendimento ao cliente da FinanceiraX S.A. Posso ajudar com análise "
            "de chamadas, satisfação de clientes, reclamações e elogios sobre nossos produtos: "
            "Seguros, Cartão de Crédito, Empréstimos, Crédito Especial e Consórcio. "
            "Há algo nessa área com que eu possa auxiliar?"
        ),
        QueryScope.BLOCKED: (
            "Desculpe, não posso ajudar com esse tema. Estou disponível para auxiliar "
            "exclusivamente na análise do atendimento ao cliente da FinanceiraX S.A., "
            "cobrindo Seguros, Cartão de Crédito, Empréstimos, Crédito Especial e Consórcio."
        ),
        QueryScope.JAILBREAK_ATTEMPT: (
            "Não posso atender a essa solicitação. Minhas diretrizes são fixas e não podem "
            "ser alteradas por instruções externas. Estou disponível para auxiliar "
            "exclusivamente na análise do atendimento ao cliente da FinanceiraX S.A."
        ),
    }

    messages_es = {
        QueryScope.IN_SCOPE: None,
        QueryScope.OUT_OF_SCOPE: (
            "Lo siento, solo puedo ayudar con operaciones de call center, interacciones con "
            "clientes y analítica de llamadas de FinanceiraX S.A. Esta solicitud está fuera "
            "de mi alcance. Puedo ayudarte con: seguros, tarjetas de crédito, préstamos, "
            "crédito especial o consorcio."
        ),
        QueryScope.BLOCKED: (
            "Lo siento, no puedo ayudar con ese tema. Puedo ayudarte con análisis de "
            "call center y atención al cliente de FinanceiraX S.A."
        ),
        QueryScope.JAILBREAK_ATTEMPT: (
            "No puedo procesar esa solicitud. Mis pautas son fijas y no se pueden cambiar. "
            "Envía una pregunta directa relacionada con las operaciones del call center de "
            "FinanceiraX S.A."
        ),
    }

    if language_key.startswith("pt"):
        return messages_pt.get(scope)
    if language_key.startswith("es"):
        return messages_es.get(scope)
    return messages_en.get(scope)
