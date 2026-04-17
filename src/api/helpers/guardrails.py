import re
import unicodedata

# Lista ampliada e normalizada de palavras-chave permitidas
ALLOWED_KEYWORDS = [
    "satisfacao", "satisfação", "cliente", "clientes", "chamada", "chamadas", "call", "sentimento", "topico", "tópico", "topicos", "tópicos",
    "atendimento", "suporte", "analise", "análise", "transcricao", "transcrição", "transcript", "contato", "central", "call center", "insight",
    "feedback", "resumo", "problema", "solucao", "solução", "tempo", "tempo medio", "tempo médio", "numero de chamadas", "número de chamadas",
    "motivo", "motivo da chamada", "billing", "conta", "plano", "opcao de plano", "opção de plano", "dispositivo", "perdido", "roubado",
    "conectividade", "internet", "parametro", "parâmetro", "indicador", "grafico", "gráfico", "chart", "dados", "data"
]

def normalize(text):
    return unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII').lower()

def is_in_scope(query: str) -> bool:
    query_norm = normalize(query)
    for keyword in ALLOWED_KEYWORDS:
        if re.search(rf"\b{normalize(keyword)}\b", query_norm):
            return True
    return False
