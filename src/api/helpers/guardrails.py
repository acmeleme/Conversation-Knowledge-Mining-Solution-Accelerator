import re
import unicodedata
import logging

logger = logging.getLogger(__name__)

# Palavras-chave do domínio financeiro e de callcenter (PT-BR) que tornam a query IN-SCOPE
ALLOWED_KEYWORDS = [
    # Callcenter genérico
    "satisfacao", "satisfacao", "cliente", "clientes", "chamada", "chamadas", "call",
    "sentimento", "topico", "topicos", "atendimento", "suporte", "analise", "transcricao",
    "transcript", "contato", "central", "callcenter", "call center", "insight", "insights",
    "feedback", "resumo", "problema", "solucao", "reclamacao", "elogio", "ocorrencia",
    "tempo", "tempo medio", "numero de chamadas", "motivo", "indicador", "grafico",
    "chart", "dados", "data", "metricas", "dashboard", "relatorio", "desempenho",
    "agente", "operador", "atendente", "protocolo", "ticket", "acionamento",
    # Produtos financeiros — Seguro
    "seguro", "apolice", "apolice", "sinistro", "cobertura", "premio", "indenizacao",
    "franquia", "vistoria", "beneficiario", "cancelamento", "contratacao de seguro",
    # Cartão de Crédito
    "cartao", "cartao de credito", "credito", "fatura", "limite", "contestacao",
    "anuidade", "bandeira", "pontos", "cashback", "cvv", "bloqueio", "desbloqueio",
    "segunda via", "pagamento", "pagamentos",
    # Empréstimos
    "emprestimo", "emprestimos", "parcelas", "taxa de juros", "cet", "amortizacao",
    "quitacao", "renegociacao", "iof", "simulacao", "inadimplencia", "atraso",
    "financiamento",
    # Crédito Especial
    "credito especial", "consignado", "credito consignado", "margem", "margem consignavel",
    "desconto em folha", "portabilidade", "inss", "portabilidade de credito",
    # Consórcio
    "consorcio", "carta de credito", "lance", "contemplacao", "cota", "grupo",
    "assembleia", "lance livre", "lance fixo",
    # Termos financeiros gerais
    "conta corrente", "conta poupanca", "extrato", "tarifas", "tarifas bancarias",
    "servico financeiro", "servicos financeiros", "financeirax", "financeira",
    "banco", "cobranca",
]

# Padrões de prompt injection e jailbreak (case-insensitive)
JAILBREAK_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|anterior|suas|prior)\s+(instructions?|instrucoes?|regras?|rules?)",
    r"forget\s+(all\s+)?(previous|anterior|suas|prior)\s+(instructions?|instrucoes?|regras?|rules?)",
    r"esqueca\s+(todas\s+)?(as\s+)?(instrucoes?|regras?|restricoes?)",
    r"ignore\s+(as\s+)?(instrucoes?|regras?|restricoes?)",
    r"you\s+are\s+now\s+(a|an|um|uma)",
    r"voce\s+e\s+(agora\s+)?(na verdade|na realidade|um|uma|o|a)\s+(?!assistente|agente|especialista)",
    r"atue\s+como",
    r"finja\s+(que\s+voce\s+)?(e|ser|esta)\s+",
    r"pretend\s+(you\s+are|to\s+be)",
    r"simulate\s+(being|that\s+you\s+are)",
    r"jailbreak",
    r"dan\s+mode",
    r"modo\s+dan",
    r"sem\s+(restricoes?|limitacoes?|filtros?)",
    r"no\s+(restrictions?|limitations?|filters?)",
    r"bypass\s+(your\s+)?(safety|guardrails?|filters?|restricoes?)",
    r"ignore\s+(safety|guardrail)",
    r"reveal\s+(your\s+)?(prompt|instructions?|system)",
    r"mostr[ae]\s+(seu|suas|os|as)\s+(prompt|instrucoes?|regras?|sistema)",
    r"repita\s+suas\s+(instrucoes?|regras?)",
    r"what\s+(are\s+your|is\s+your)\s+(system\s+prompt|instructions?)",
    r"quais\s+(sao\s+)?suas\s+instrucoes",
]

# Tópicos claramente off-topic
OFF_TOPIC_PATTERNS = [
    r"\breceita\s+(de\s+)?(bolo|cozinha|culinaria|comida)\b",
    r"\bprograma[a-z]*\s+(de\s+)?tv\b",
    r"\bprevisao\s+do\s+tempo\b",
    r"\bclima\s+amanha\b",
    r"\bcomo\s+(fazer|cozinhar|preparar)\s+",
    r"\bpiada\b",
    r"\bhistoria\s+(de\s+)?horror\b",
    r"\bescreva\s+(um|uma)\s+(poema|musica|conto|historia)\b",
    r"\bwrite\s+(a|an)\s+(poem|song|story|joke)\b",
    r"\bcapital\s+(da|de|do)\b",
    r"\b(populacao|area)\s+(da|de|do)\s+[a-z]+\b",
    r"\bquem\s+inventou\b",
    r"\bwho\s+invented\b",
]


def normalize(text: str) -> str:
    return unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII').lower()


def is_jailbreak_attempt(query: str) -> bool:
    """Detecta tentativas de prompt injection ou jailbreak."""
    query_lower = query.lower()
    for pattern in JAILBREAK_PATTERNS:
        if re.search(pattern, query_lower, re.IGNORECASE):
            logger.warning("Jailbreak attempt detected: pattern '%s' matched in query: %s", pattern, query[:100])
            return True
    return False


def is_off_topic(query: str) -> bool:
    """Detecta perguntas claramente fora do domínio financeiro."""
    query_lower = query.lower()
    for pattern in OFF_TOPIC_PATTERNS:
        if re.search(pattern, query_lower, re.IGNORECASE):
            return True
    return False


def is_in_scope(query: str) -> bool:
    """
    Retorna True se a query for in-scope para o domínio financeiro/callcenter.
    Usa lista de permissões expansiva para evitar falsos positivos.
    """
    query_norm = normalize(query)
    for keyword in ALLOWED_KEYWORDS:
        if normalize(keyword) in query_norm:
            return True
    return False


def get_guardrail_response(query: str) -> str | None:
    """
    Avalia a query e retorna uma resposta de recusa educada em PT-BR se fora do escopo,
    ou None se a query for permitida.
    """
    if is_jailbreak_attempt(query):
        logger.warning("Blocked jailbreak attempt: %s", query[:100])
        return (
            "Peço desculpas, mas não posso atender a essa solicitação. "
            "Minha função é auxiliar exclusivamente nas análises de atendimento ao cliente da FinanceiraX S.A. "
            "Se precisar de ajuda com dados de chamadas, sentimentos, reclamações ou elogios, estou à disposição! 😊"
        )

    if is_off_topic(query):
        logger.info("Blocked off-topic query: %s", query[:100])
        return (
            "Desculpe, esse assunto está fora do meu escopo de atuação. "
            "Sou especialista em análise de atendimento ao cliente da FinanceiraX S.A. — posso ajudar com "
            "análise de chamadas, satisfação de clientes, reclamações e elogios sobre nossos produtos financeiros "
            "(Seguros, Cartão de Crédito, Empréstimos, Crédito Especial e Consórcio). "
            "Há algo nessa área com que eu possa auxiliar?"
        )

    return None  # Query permitida
