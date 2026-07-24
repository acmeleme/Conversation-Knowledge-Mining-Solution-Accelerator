from azure.ai.agents.models import AzureAISearchTool, AzureAISearchQueryType
from azure.ai.projects import AIProjectClient

from agents.agent_factory_base import BaseAgentFactory
from auth.auth_utils import get_current_restricted_topics
from common.config.config import Config

from helpers.azure_credential_utils import get_azure_credential


class SearchAgentFactory(BaseAgentFactory):
    """Factory class for creating search agents with Azure AI Search integration."""
    _agent_pool: dict[str, dict] = {}

    @staticmethod
    def _escape_odata_string(value: str) -> str:
        return value.replace("'", "''")

    @classmethod
    def _build_search_filter(cls) -> str:
        restricted_topics = get_current_restricted_topics()
        if not restricted_topics:
            return ""

        return " and ".join(
            f"topic ne '{cls._escape_odata_string(topic)}'"
            for topic in restricted_topics
        )

    @classmethod
    async def get_agent(cls) -> object:
        """Get or create a search agent instance keyed by the active request restrictions."""
        async with cls._lock:
            search_filter = cls._build_search_filter()
            agent_key = search_filter or "__default__"
            if agent_key not in cls._agent_pool:
                config = Config()
                cls._agent_pool[agent_key] = await cls.create_agent(
                    config,
                    search_filter=search_filter,
                )
            return cls._agent_pool[agent_key]

    @classmethod
    async def delete_agent(cls):
        """Delete every cached search agent instance."""
        async with cls._lock:
            for agent_wrapper in list(cls._agent_pool.values()):
                await cls._delete_agent_instance(agent_wrapper)
            cls._agent_pool.clear()

    @classmethod
    async def create_agent(cls, config, search_filter: str = ""):
        """
        Asynchronously creates a search agent using Azure AI Search and registers it
        with the provided project configuration.

        Args:
            config: Configuration object containing Azure project and search index settings.

        Returns:
            dict: A dictionary containing the created agent and the project client.
        """
        project_client = AIProjectClient(
            endpoint=config.ai_project_endpoint,
            credential=get_azure_credential(client_id=config.azure_client_id),
            api_version=config.ai_project_api_version,
        )

        field_mapping = {
            "contentFields": ["content", "summary"],
            "urlField": "sourceurl",
            "titleField": "topic",
        }

        project_index = project_client.indexes.create_or_update(
            name=f"project-index-{config.azure_ai_search_connection_name}-{config.azure_ai_search_index}",
            version="1",
            index={
                "connectionName": config.azure_ai_search_connection_name,
                "indexName": config.azure_ai_search_index,
                "type": "AzureSearch",
                "fieldMapping": field_mapping
            }
        )

        ai_search = AzureAISearchTool(
            index_asset_id=f"{project_index.name}/versions/{project_index.version}",
            index_connection_id=None,
            index_name=None,
            query_type=AzureAISearchQueryType.SIMPLE,
            top_k=10,
            filter=search_filter,
        )

        agent_instructions = (
            "Você é um assistente especializado em análise de transcrições do callcenter da FinanceiraX S.A. "
            "Sua função é buscar e sintetizar informações das transcrições de chamadas indexadas. "
            "Sempre use a ferramenta de busca para encontrar dados relevantes antes de responder. "
            "Ao receber uma pergunta sobre um tópico (ex: Seguro, Sinistros, Cartão, Empréstimo), "
            "busque tanto pelo nome exato quanto por termos relacionados (ex: sinistro, indenização, seguro). "
            "Se a busca retornar resultados, sintetize-os em um resumo estruturado com: "
            "1) principais queixas ou motivos de contato, 2) sentimento geral, 3) exemplos concretos das transcrições. "
            "Sempre cite as fontes encontradas. Responda em português brasileiro."
        )
        if search_filter:
            agent_instructions += (
                " Restrições de acesso estão ativas para este usuário. "
                "Nunca utilize, cite ou resuma documentos cujo tópico tenha sido excluído pelo filtro do Azure AI Search."
            )

        agent = project_client.agents.create_agent(
            model=config.azure_openai_deployment_model,
            name=f"KM-ChatWithCallTranscriptsAgent-{config.solution_name}",
            instructions=agent_instructions,
            tools=ai_search.definitions,
            tool_resources=ai_search.resources,
        )

        return {
            "agent": agent,
            "client": project_client
        }

    @classmethod
    async def _delete_agent_instance(cls, agent_wrapper: dict):
        """
        Asynchronously deletes the specified agent instance from the Azure AI project.

        Args:
            agent_wrapper (dict): A dictionary containing the 'agent' and the corresponding 'client'.
        """
        agent_wrapper["client"].agents.delete_agent(agent_wrapper["agent"].id)
