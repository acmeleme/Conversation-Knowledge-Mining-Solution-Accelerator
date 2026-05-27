import os
from promptflow.core import tool
from azure.search.documents import SearchClient
from azure.search.documents.models import (
    VectorizableTextQuery,
    QueryType,
    QueryCaptionType,
    QueryAnswerType,
)
from azure.core.credentials import AzureKeyCredential


@tool
def search_km_data(user_question: str) -> str:
    """
    Queries the km_processed_data Azure AI Search index using
    vector + semantic hybrid search (top-5) and returns a
    formatted string of results for the LLM node.
    """
    endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
    key = os.environ["AZURE_SEARCH_KEY"]
    index_name = os.environ.get("AZURE_SEARCH_INDEX", "km_processed_data")

    credential = AzureKeyCredential(key)
    client = SearchClient(
        endpoint=endpoint,
        index_name=index_name,
        credential=credential,
    )

    # Vector + semantic hybrid query
    vector_query = VectorizableTextQuery(
        text=user_question,
        k_nearest_neighbors=50,        # Candidates for fusion
        fields="content_vector",       # Adjust to your index vector field name
        exhaustive=False,
    )

    results = client.search(
        search_text=user_question,
        vector_queries=[vector_query],
        query_type=QueryType.SEMANTIC,
        semantic_configuration_name="km-semantic-config",  # Adjust to your config
        query_caption=QueryCaptionType.EXTRACTIVE,
        query_answer=QueryAnswerType.EXTRACTIVE,
        select=["chunk_id", "content", "source_file", "call_date", "agent_id"],
        top=5,
    )

    formatted_chunks = []
    for i, result in enumerate(results, start=1):
        chunk_id = result.get("chunk_id", f"chunk_{i}")
        content = result.get("content", "").strip()
        source_file = result.get("source_file", "unknown")
        call_date = result.get("call_date", "")
        agent_id = result.get("agent_id", "")
        score = result.get("@search.reranker_score") or result.get("@search.score", 0)

        chunk_text = (
            f"[Result {i}]\n"
            f"chunk_id: {chunk_id}\n"
            f"source_file: {source_file}\n"
            f"call_date: {call_date}\n"
            f"agent_id: {agent_id}\n"
            f"relevance_score: {round(float(score), 4)}\n"
            f"content:\n{content}\n"
        )
        formatted_chunks.append(chunk_text)

    if not formatted_chunks:
        return (
            "No relevant results found in the knowledge base for this query. "
            "Please rephrase the question or verify the index contains data."
        )

    header = (
        f"## Azure AI Search Results\n"
        f"Index: {index_name} | Query: \"{user_question}\" | "
        f"Mode: Vector + Semantic Hybrid | Top: {len(formatted_chunks)}\n\n"
    )

    return header + "\n---\n".join(formatted_chunks)
