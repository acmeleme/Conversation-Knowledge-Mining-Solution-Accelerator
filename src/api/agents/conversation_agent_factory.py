from semantic_kernel.agents import AzureAIAgent, AzureAIAgentThread, AzureAIAgentSettings

from services.chat_service import ChatService
from plugins.chat_with_data_plugin import ChatWithDataPlugin
from agents.agent_factory_base import BaseAgentFactory

from helpers.azure_credential_utils import get_azure_credential_async
from helpers.guardrails_config import AGENT_GUARDRAIL_INSTRUCTIONS


class ConversationAgentFactory(BaseAgentFactory):
    """Factory class for creating conversation agents with semantic kernel integration."""

    @classmethod
    async def create_agent(cls, config):
        """
        Asynchronously creates and returns an AzureAIAgent instance configured with
        the appropriate model, instructions, and plugin for conversation support.

        Args:
            config: Configuration object containing solution-specific settings.

        Returns:
            AzureAIAgent: An initialized agent ready for handling conversation threads.
        """
        ai_agent_settings = AzureAIAgentSettings()
        creds = await get_azure_credential_async(client_id=config.azure_client_id)
        client = AzureAIAgent.create_client(credential=creds, endpoint=ai_agent_settings.endpoint)

        agent_name = f"KM-ConversationKnowledgeAgent-{config.solution_name}"
        agent_instructions = '''Voce e um assistente especializado em mineracao de conhecimento de callcenter e analise de atendimento ao cliente para a FinanceiraX S.A., uma empresa brasileira de servicos financeiros. Responda sempre em Portugues (PT-BR), a menos que o usuario solicite explicitamente outro idioma.
        Sempre retorne as citacoes como estao na resposta final.
        Sempre retorne os marcadores de citacao exatamente como aparecem nos dados de origem, colocados no campo "answer" no local correto. Nao modifique, converta ou simplifique esses marcadores.
        Inclua marcadores de citacao apenas se suas fontes estiverem presentes na lista "citations". Inclua fontes na lista "citations" apenas se forem usadas na resposta.
        Use a estrutura { "answer": "", "citations": [ {"url":"","title":""} ] }.
        Voce pode usar o historico de conversa anterior para entender o contexto e esclarecer perguntas de acompanhamento.
        Quando o usuario pedir um resumo ou plano de acao, forneca um paragrafo conciso seguido de pontos com descobertas concretas e proximas acoes.

        REGRA OBRIGATORIA — SEMPRE CHAME GetCallInsights para qualquer pergunta sobre estes topicos do callcenter:
        - Seguro — Contratacao e Cancelamento
        - Seguro — Sinistros e Indenizacoes
        - Cartao de Credito — Fatura e Pagamento
        - Cartao de Credito — Bloqueio e Contestacao
        - Emprestimos — Simulacao e Contratacao
        - Emprestimos — Renegociacao e Inadimplencia
        - Credito Especial — Credito Consignado
        - Credito Especial — Portabilidade de Credito
        - Consorcio — Carta de Credito e Contemplacao
        - Consorcio — Duvidas sobre Grupo e Cota
        Estas sao CATEGORIAS DE ATENDIMENTO no banco de dados do callcenter da FinanceiraX S.A. Nao sao produtos de consumo geral.
        Sempre que um usuario perguntar sobre resumo, analise, sentimento ou insights sobre QUALQUER um desses topicos, voce DEVE chamar GetCallInsights imediatamente e usar os resultados para construir sua resposta.
        Mesmo que GetCallInsights retorne dados limitados, forneca uma resposta de melhor esforco com base no que foi recuperado.
        NUNCA recuse responder uma pergunta sobre esses topicos. NUNCA diga que nao pode fornecer resumos sobre eles.

        Para perguntas que exigem dados numericos (contagens, medias, tendencias), use GetDatabaseMetrics.
        Para solicitacoes de visualizacao de dados ou graficos, use GenerateChartData.

        Ao chamar uma funcao ou plugin, inclua todos os detalhes originais especificados pelo usuario exatamente na string de entrada da funcao.
        SOMENTE para perguntas que solicitam explicitamente graficos ou visualizacoes, garanta que o campo "answer" contenha o objeto JSON bruto.
        Voce nao deve repetir declaracoes de importacao, blocos de codigo ou frases nas respostas.

        ''' + AGENT_GUARDRAIL_INSTRUCTIONS

        agent_definition = await client.agents.create_agent(
            model=ai_agent_settings.model_deployment_name,
            name=agent_name,
            instructions=agent_instructions
        )

        return AzureAIAgent(
            client=client,
            definition=agent_definition,
            plugins=[ChatWithDataPlugin()]
        )

    @classmethod
    async def _delete_agent_instance(cls, agent: AzureAIAgent):
        """
        Asynchronously deletes all associated threads from the agent instance and then deletes the agent.

        Args:
            agent (AzureAIAgent): The agent instance whose threads and definition need to be removed.
        """
        thread_cache = getattr(ChatService, "thread_cache", None)
        if thread_cache:
            for conversation_id, thread_id in list(thread_cache.items()):
                try:
                    thread = AzureAIAgentThread(client=agent.client, thread_id=thread_id)
                    await thread.delete()
                except Exception as e:
                    print(f"Failed to delete thread {thread_id} for {conversation_id}: {e}")
        await agent.client.agents.delete_agent(agent.id)
