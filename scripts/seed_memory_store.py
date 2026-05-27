#!/usr/bin/env python3
"""
Script para popular o Azure AI Foundry Memory Store com conversas simuladas de call center.

Gera 100 conversas realistas em português brasileiro com diferentes temas.
Cada conversa cria DOIS tipos de memória:
- **user_profile**: Informações sobre o cliente/empresa (plano, preferências, etc.)
- **chat_summary**: Resumo do que foi discutido naquela conversa específica

CATEGORIAS:
- Vendas e consultas de produtos
- Suporte técnico
- Reclamações e problemas
- Consultas de status de pedidos
- Informações de conta

USO:
    python scripts/seed_memory_store.py

REQUISITOS:
    - azure-ai-projects instalado
    - Variáveis de ambiente configuradas:
        - AZURE_AI_PROJECT_ENDPOINT
        - AZURE_AI_MEMORY_STORE_NAME (deve ser "memory-store-callcenter-100")
        - AZURE_CLIENT_ID (opcional)

SCOPE:
    O script usa o scope: tenant_2e50c5c4-4293-4a30-8a9c-0d9fb964a55a__user_1e7cc145-ed07-4f8a-8779-502ad993ccf5
"""

import asyncio
import logging
import os
import random
import sys
import time
from typing import List, Tuple

try:
    from azure.ai.projects import AIProjectClient
    from azure.core.credentials import AzureKeyCredential
    from azure.identity import DefaultAzureCredential
except ImportError:
    print("❌ ERRO: azure-ai-projects não está instalado.")
    print("Execute: pip install azure-ai-projects")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Configuração
MEMORY_STORE_NAME = os.getenv("AZURE_AI_MEMORY_STORE_NAME", "memory-store-callcenter-100")
PROJECT_ENDPOINT = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")

# Scope fixo conforme especificado
SCOPE = "tenant_2e50c5c4-4293-4a30-8a9c-0d9fb964a55a__user_1e7cc145-ed07-4f8a-8779-502ad993ccf5"

# Configurações de retry
MAX_RETRIES = 3
RETRY_DELAY_BASE = 2  # segundos
UPDATE_DELAY_SECONDS = 5

# Templates de conversas por categoria
CONVERSAS_VENDAS = [
    (
        "Bom dia, gostaria de saber mais sobre o novo plano Premium que vocês lançaram.",
        "Olá! Claro, o plano Premium oferece armazenamento ilimitado, suporte prioritário 24/7 e acesso antecipado a novos recursos. O valor é R$ 49,90/mês. Gostaria de conhecer mais detalhes?"
    ),
    (
        "Vocês têm desconto para assinatura anual?",
        "Sim! Temos 20% de desconto para pagamento anual. O plano Premium fica R$ 479,00/ano ao invés de R$ 598,80. Quer que eu prepare uma proposta?"
    ),
    (
        "Qual a diferença entre o plano Basic e o Professional?",
        "O Basic tem 10GB de armazenamento e suporte por email. Já o Professional oferece 100GB, suporte prioritário e recursos avançados de colaboração. É perfeito para equipes!"
    ),
]

CONVERSAS_SUPORTE = [
    (
        "Não consigo fazer login na minha conta, aparece erro 401.",
        "Entendo a frustração. O erro 401 geralmente indica problema de autenticação. Você pode tentar: 1) Limpar cache do navegador 2) Resetar sua senha 3) Usar navegação anônima. Qual dessas opções você prefere tentar primeiro?"
    ),
    (
        "Meu aplicativo trava quando tento fazer upload de arquivos grandes.",
        "Vou te ajudar com isso. Arquivos acima de 100MB precisam de configuração especial. Qual o tamanho do arquivo que você está tentando enviar?"
    ),
    (
        "A sincronização dos dados está muito lenta hoje.",
        "Verificamos nossos servidores e identificamos uma lentidão temporária na região Sul. Nossa equipe técnica já está trabalhando nisso. Previsão de normalização em 1 hora. Posso notificá-lo quando estiver resolvido?"
    ),
]

CONVERSAS_RECLAMACOES = [
    (
        "Estou muito insatisfeito! Fui cobrado duas vezes este mês!",
        "Peço sinceras desculpas por este transtorno. Vou verificar imediatamente sua fatura. Pode me informar o número do seu pedido ou CPF?"
    ),
    (
        "Solicitei cancelamento há 5 dias e ainda não foi processado!",
        "Lamento muito por essa demora. Vou escalar seu caso para prioridade máxima. Normalmente o processamento leva 2 dias úteis. Vou garantir que seja finalizado hoje mesmo."
    ),
    (
        "A qualidade do serviço caiu muito nos últimos meses.",
        "Sua opinião é muito importante para nós. Pode me detalhar quais aspectos você notou piora? Queremos entender para melhorar."
    ),
]

CONVERSAS_STATUS = [
    (
        "Qual o status do meu pedido #12345?",
        "Deixa eu verificar para você... Seu pedido está em processamento e tem previsão de envio para amanhã. Você receberá o código de rastreamento por email."
    ),
    (
        "Meu reembolso foi aprovado quando?",
        "Consultando aqui... Seu reembolso foi aprovado em 18/05/2026 e o valor de R$ 79,90 deve aparecer na sua conta em até 5 dias úteis."
    ),
    (
        "Quando vence minha assinatura atual?",
        "Sua assinatura do plano Professional está ativa e renova automaticamente em 15/06/2026. Quer que eu envie um lembrete uma semana antes?"
    ),
]

CONVERSAS_CONTA = [
    (
        "Como faço para atualizar meu email de contato?",
        "É bem simples! Você pode atualizar em Configurações > Perfil > Email. Ou posso fazer isso para você agora, qual o novo email?"
    ),
    (
        "Preciso adicionar outro usuário na minha conta corporativa.",
        "Perfeito! No plano Professional você pode ter até 5 usuários. Acesse Equipe > Adicionar Membro e envie o convite por email. Precisa de ajuda nesse processo?"
    ),
    (
        "Como exporto meus dados da plataforma?",
        "Você pode exportar em Configurações > Dados > Exportar. Selecione o período e formato (CSV ou JSON). O arquivo fica pronto em até 24h e você recebe por email."
    ),
]

# Conversas complementares para variedade
CONVERSAS_EXTRAS = [
    (
        "Vocês aceitam pagamento via PIX?",
        "Sim, aceitamos PIX, cartão de crédito, débito e boleto bancário. O PIX tem aprovação instantânea!"
    ),
    (
        "Há integração com o Slack?",
        "Sim! Temos integração nativa com Slack, Teams, Discord e outras ferramentas. Quer que eu envie o guia de configuração?"
    ),
    (
        "Minha empresa precisa de nota fiscal. Como solicito?",
        "Claro! Basta informar o CNPJ no momento da compra ou me passar agora que emito retroativamente. Qual seu CNPJ?"
    ),
    (
        "O aplicativo mobile está disponível para iOS?",
        "Sim, temos app para iOS e Android. Você encontra na App Store como 'ConversaAI'. Já tem mais de 50 mil downloads!"
    ),
    (
        "Posso fazer downgrade do meu plano?",
        "Sim, você pode alterar para um plano inferior a qualquer momento. A diferença é creditada proporcionalmente. Quer que eu faça isso agora?"
    ),
    (
        "Quantos dispositivos posso usar simultaneamente?",
        "No plano Basic são 2 dispositivos, Professional até 5 e Premium ilimitado. Seu plano atual é Basic."
    ),
    (
        "Tem algum tutorial em vídeo para iniciantes?",
        "Temos sim! Nossa playlist 'Primeiros Passos' no YouTube tem 15 vídeos curtos. Quer que eu envie o link?"
    ),
    (
        "A ferramenta é compatível com LGPD?",
        "Totalmente! Somos certificados ISO 27001 e em compliance com LGPD. Todos os dados ficam em servidores no Brasil."
    ),
]


def get_credential():
    """Obtém credencial do Azure."""
    if AZURE_CLIENT_ID:
        return DefaultAzureCredential(managed_identity_client_id=AZURE_CLIENT_ID)
    return DefaultAzureCredential()


def create_client():
    """Cria cliente do Azure AI Projects."""
    if not PROJECT_ENDPOINT:
        logger.error("AZURE_AI_PROJECT_ENDPOINT não está configurado!")
        sys.exit(1)
    
    credential = get_credential()
    
    try:
        # Tenta com allow_preview primeiro
        return AIProjectClient(
            endpoint=PROJECT_ENDPOINT,
            credential=credential,
            allow_preview=True
        )
    except TypeError:
        # Fallback para versão sem allow_preview
        return AIProjectClient(
            endpoint=PROJECT_ENDPOINT,
            credential=credential
        )


def gerar_conversas() -> List[Tuple[str, str, str]]:
    """Gera lista de 100 conversas variadas com categoria."""
    todas_conversas = []
    
    # Adiciona todas as categorias com seus nomes
    categorias = {
        "vendas": CONVERSAS_VENDAS,
        "suporte": CONVERSAS_SUPORTE,
        "reclamações": CONVERSAS_RECLAMACOES,
        "status": CONVERSAS_STATUS,
        "conta": CONVERSAS_CONTA,
        "extras": CONVERSAS_EXTRAS
    }
    
    # Combina todas as conversas base com suas categorias
    base_conversas = []
    for cat_nome, cat_conversas in categorias.items():
        for conversa in cat_conversas:
            base_conversas.append((conversa[0], conversa[1], cat_nome))
    
    # Gera 100 conversas com repetição e variação
    while len(todas_conversas) < 100:
        # Escolhe conversa aleatória
        conversa = random.choice(base_conversas)
        
        # Adiciona pequenas variações
        user_msg = conversa[0]
        assistant_msg = conversa[1]
        categoria = conversa[2]
        
        # Varia saudações
        saudacoes_inicio = ["", "Olá! ", "Oi! ", "Bom dia! ", "Boa tarde! "]
        saudacoes_fim = ["", " Obrigado!", " Agradeço!", " Valeu!", " Muito obrigado!"]
        
        if random.random() > 0.5:
            user_msg = random.choice(saudacoes_inicio) + user_msg + random.choice(saudacoes_fim)
        
        todas_conversas.append((user_msg, assistant_msg, categoria))
    
    return todas_conversas[:100]


def gerar_chat_summary(user_text: str, assistant_text: str, categoria: str) -> str:
    """Gera um resumo da conversa para o chat summary."""
    summaries_por_categoria = {
        "vendas": [
            "Cliente interessado em upgrade para plano Premium",
            "Consulta sobre descontos para assinatura anual",
            "Comparação entre planos Basic e Professional",
            "Interesse em conhecer novos recursos do produto"
        ],
        "suporte": [
            "Problema de login resolvido com reset de senha",
            "Dificuldade com upload de arquivos grandes",
            "Lentidão na sincronização - problema de servidor identificado",
            "Erro de autenticação corrigido"
        ],
        "reclamações": [
            "Cobrança duplicada - caso escalado para reembolso",
            "Atraso no cancelamento - prioridade máxima",
            "Feedback sobre queda de qualidade do serviço",
            "Insatisfação com tempo de resposta"
        ],
        "status": [
            "Consulta de status de pedido #12345 - em processamento",
            "Verificação de reembolso aprovado em 18/05",
            "Data de renovação de assinatura confirmada",
            "Rastreamento de envio solicitado"
        ],
        "conta": [
            "Atualização de email de contato",
            "Adição de novo usuário na conta corporativa",
            "Orientação sobre exportação de dados",
            "Configuração de perfil atualizada"
        ],
        "extras": [
            "Informações sobre métodos de pagamento - PIX disponível",
            "Consulta sobre integração com Slack",
            "Emissão de nota fiscal com CNPJ",
            "Download de aplicativo mobile orientado"
        ]
    }
    
    return random.choice(summaries_por_categoria.get(categoria, summaries_por_categoria["extras"]))


def gerar_user_profile(categoria: str) -> str:
    """Gera informações de perfil do usuário."""
    profiles = [
        "Empresa no plano Premium, prefere comunicação em português, usa CNPJ para fins fiscais",
        "Cliente pessoa física no plano Basic, interessado em upgrade, acessa via mobile",
        "Conta corporativa Professional com 3 usuários, integra com Slack e Teams",
        "Startup em fase de crescimento, plano Professional, prioriza suporte técnico rápido",
        "Empresa estabelecida no plano Enterprise, compliance LGPD crítico, dados no Brasil",
        "Freelancer autônomo, plano Basic, foco em custo-benefício e simplicidade",
        "Média empresa, plano Professional, necessita nota fiscal mensal",
        "Cliente Premium desde 2024, alto volume de dados, usa todos os recursos",
        "Novo cliente em teste gratuito, avaliando migração do concorrente",
        "Cliente corporativo com contrato anual, pagamento via boleto, 10 usuários ativos"
    ]
    
    return random.choice(profiles)


async def update_memory_with_retry(
    client: AIProjectClient,
    scope: str,
    user_text: str,
    assistant_text: str,
    categoria: str = "extras",
    attempt: int = 1
) -> bool:
    """Atualiza memória com retry logic para rate limits."""
    items = [
        {"role": "user", "type": "message", "content": user_text},
        {"role": "assistant", "type": "message", "content": assistant_text},
    ]
    
    try:
        def _update():
            return client.beta.memory_stores.begin_update_memories(
                name=MEMORY_STORE_NAME,
                scope=scope,
                items=items,
                update_delay=UPDATE_DELAY_SECONDS,
            )
        
        # Executa em thread separada para não bloquear
        poller = await asyncio.to_thread(_update)
        return True
        
    except Exception as e:
        error_msg = str(e).lower()
        
        # Verifica se é rate limit
        if "429" in error_msg or "rate limit" in error_msg or "throttl" in error_msg:
            if attempt < MAX_RETRIES:
                delay = RETRY_DELAY_BASE ** attempt
                logger.warning(f"Rate limit atingido. Tentativa {attempt}/{MAX_RETRIES}. Aguardando {delay}s...")
                await asyncio.sleep(delay)
                return await update_memory_with_retry(client, scope, user_text, assistant_text, categoria, attempt + 1)
            else:
                logger.error(f"Rate limit após {MAX_RETRIES} tentativas. Pulando esta conversa.")
                return False
        else:
            logger.error(f"Erro ao atualizar memória: {e}")
            return False


async def seed_conversations():
    """Função principal para popular o memory store."""
    logger.info("=" * 60)
    logger.info("🚀 Iniciando população do Memory Store")
    logger.info("=" * 60)
    logger.info(f"Memory Store: {MEMORY_STORE_NAME}")
    logger.info(f"Scope: {SCOPE}")
    logger.info(f"Endpoint: {PROJECT_ENDPOINT}")
    logger.info("")
    
    # Cria cliente
    try:
        client = create_client()
        logger.info("✅ Cliente Azure AI Projects criado com sucesso")
    except Exception as e:
        logger.error(f"❌ Erro ao criar cliente: {e}")
        sys.exit(1)
    
    # Gera conversas
    conversas = gerar_conversas()
    logger.info(f"📝 {len(conversas)} conversas geradas (cada uma cria user_profile + chat_summary)")
    logger.info("")
    
    # Processa conversas
    sucesso = 0
    falhas = 0
    inicio = time.time()
    
    for i, (user_msg, assistant_msg, categoria) in enumerate(conversas, 1):
        # Mostra progresso a cada 10 conversas
        if i % 10 == 0:
            logger.info(f"📊 Progresso: {i}/100 conversas processadas")
        
        # Atualiza memória com a conversa
        result = await update_memory_with_retry(client, SCOPE, user_msg, assistant_msg, categoria)
        
        if result:
            sucesso += 1
        else:
            falhas += 1
        
        # Pequeno delay entre conversas para evitar throttling
        if i < len(conversas):
            await asyncio.sleep(0.5)
    
    # Relatório final
    duracao = time.time() - inicio
    logger.info("")
    logger.info("=" * 60)
    logger.info("✨ População do Memory Store concluída!")
    logger.info("=" * 60)
    logger.info(f"✅ Conversas criadas com sucesso: {sucesso}/100")
    logger.info(f"📋 Tipos de memória gerados: user_profile + chat_summary")
    if falhas > 0:
        logger.info(f"❌ Falhas: {falhas}/100")
    logger.info(f"⏱️  Tempo total: {duracao:.1f} segundos")
    logger.info(f"📈 Média: {duracao/100:.2f} segundos por conversa")
    logger.info("")
    logger.info("🔍 Verifique as memórias no portal do Azure AI Foundry:")
    logger.info(f"   Memory Store: {MEMORY_STORE_NAME}")
    logger.info(f"   Scope: {SCOPE}")
    logger.info(f"   Kind: user_profile (perfil) e chat_summary (resumo de conversa)")
    logger.info("=" * 60)


def main():
    """Entry point."""
    try:
        asyncio.run(seed_conversations())
    except KeyboardInterrupt:
        logger.info("\n⚠️  Operação cancelada pelo usuário")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Erro fatal: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
