"""
Script de carga de dados: FinanceiraX S.A. → Azure Search + SQL DB
Usa DefaultAzureCredential (az login) — sem dependência de Key Vault
"""

import json
import struct
import time
import re
import sys
import os

import pyodbc
import pandas as pd
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchField, SearchFieldDataType, VectorSearch,
    HnswAlgorithmConfiguration, VectorSearchProfile,
    AzureOpenAIVectorizer, AzureOpenAIVectorizerParameters,
    SemanticConfiguration, SemanticSearch, SemanticPrioritizedFields,
    SemanticField, SearchIndex
)
from openai import AzureOpenAI

# ── Configurações (sem Key Vault) ──────────────────────────────────────────────
SEARCH_ENDPOINT = "https://srch-financeirax01.search.windows.net"
INDEX_NAME = "call_transcripts_index"

OPENAI_ENDPOINT = "https://aif-financeirax01.openai.azure.com/"
OPENAI_API_VERSION = "2025-01-01-preview"
EMBEDDING_MODEL = "text-embedding-ada-002"
GPT_MODEL = "gpt-4o-mini"

SQL_SERVER = "sql-financeirax01.database.windows.net"
SQL_DATABASE = "sqldb-financeirax01"
SQL_DRIVER = "{ODBC Driver 17 for SQL Server}"

# Caminhos relativos ao repositório
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROCESSED_DATA_FILE = os.path.join(REPO_ROOT, "infra", "data", "sample_processed_data.json")

print("=" * 60)
print("  FinanceiraX S.A. — Carga de Dados Azure")
print("=" * 60)
print(f"Repo root: {REPO_ROOT}")

# ── Credencial ─────────────────────────────────────────────────────────────────
credential = DefaultAzureCredential()
print("\n✓ DefaultAzureCredential criada (usa az login)")

# ── OpenAI client ──────────────────────────────────────────────────────────────
token_provider = get_bearer_token_provider(
    credential, "https://cognitiveservices.azure.com/.default"
)
openai_client = AzureOpenAI(
    azure_endpoint=OPENAI_ENDPOINT,
    azure_ad_token_provider=token_provider,
    api_version=OPENAI_API_VERSION,
)
print("✓ Azure OpenAI client configurado")

# ── Azure Search clients ───────────────────────────────────────────────────────
index_client = SearchIndexClient(endpoint=SEARCH_ENDPOINT, credential=credential)
search_client = SearchClient(endpoint=SEARCH_ENDPOINT, index_name=INDEX_NAME, credential=credential)
print("✓ Azure Search clients configurados")

# ── SQL connection via token ───────────────────────────────────────────────────
def get_sql_connection():
    token_bytes = credential.get_token("https://database.windows.net/.default").token.encode("utf-16-LE")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
    SQL_COPT_SS_ACCESS_TOKEN = 1256
    conn_str = f"DRIVER={SQL_DRIVER};SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};"
    return pyodbc.connect(conn_str, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})

conn = get_sql_connection()
cursor = conn.cursor()
print("✓ SQL Server conectado")

# ═══════════════════════════════════════════════════════════════════════════════
# PASSO 1: Criar índice Azure Search
# ═══════════════════════════════════════════════════════════════════════════════
def create_search_index():
    print("\n── Passo 1: Criar índice Azure Search ─────────────────────")
    fields = [
        SearchField(name="id", type=SearchFieldDataType.String, key=True),
        SearchField(name="chunk_id", type=SearchFieldDataType.String, filterable=True),
        SearchField(name="content", type=SearchFieldDataType.String, searchable=True),
        SearchField(name="sourceurl", type=SearchFieldDataType.String, filterable=True),
        SearchField(
            name="contentVector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            vector_search_dimensions=1536,
            vector_search_profile_name="myHnswProfile"
        )
    ]
    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="myHnsw")],
        profiles=[VectorSearchProfile(
            name="myHnswProfile",
            algorithm_configuration_name="myHnsw",
            vectorizer_name="myOpenAI"
        )],
        vectorizers=[AzureOpenAIVectorizer(
            vectorizer_name="myOpenAI",
            kind="azureOpenAI",
            parameters=AzureOpenAIVectorizerParameters(
                resource_url=OPENAI_ENDPOINT,
                deployment_name=EMBEDDING_MODEL,
                model_name=EMBEDDING_MODEL
            )
        )]
    )
    semantic_config = SemanticConfiguration(
        name="my-semantic-config",
        prioritized_fields=SemanticPrioritizedFields(
            content_fields=[SemanticField(field_name="content")]
        )
    )
    index = SearchIndex(
        name=INDEX_NAME,
        fields=fields,
        vector_search=vector_search,
        semantic_search=SemanticSearch(configurations=[semantic_config])
    )
    try:
        existing = index_client.get_index(INDEX_NAME)
        index_client.delete_index(INDEX_NAME)
        print(f"  → Índice existente '{INDEX_NAME}' deletado")
        time.sleep(2)
    except Exception:
        pass
    index_client.create_index(index)
    print(f"  ✓ Índice '{INDEX_NAME}' criado com sucesso")

create_search_index()

# ═══════════════════════════════════════════════════════════════════════════════
# PASSO 2: Criar tabelas SQL
# ═══════════════════════════════════════════════════════════════════════════════
def create_tables():
    print("\n── Passo 2: Criar tabelas SQL ─────────────────────────────")
    tables = [
        "processed_data", "processed_data_key_phrases",
        "km_mined_topics", "km_processed_data"
    ]
    for t in tables:
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {t}")
            conn.commit()
        except Exception as e:
            print(f"  ! Aviso ao dropar {t}: {e}")

    cursor.execute("""CREATE TABLE processed_data (
        ConversationId varchar(255) NOT NULL PRIMARY KEY,
        EndTime varchar(255),
        StartTime varchar(255),
        Content varchar(max),
        summary varchar(3000),
        satisfied varchar(255),
        sentiment varchar(255),
        topic varchar(255),
        key_phrases nvarchar(max),
        complaint varchar(255),
        mined_topic varchar(255)
    )""")

    cursor.execute("""CREATE TABLE processed_data_key_phrases (
        ConversationId varchar(255),
        key_phrase varchar(500),
        sentiment varchar(255),
        topic varchar(255),
        StartTime varchar(255)
    )""")

    cursor.execute("""CREATE TABLE km_mined_topics (
        label varchar(255) NOT NULL PRIMARY KEY,
        description varchar(500)
    )""")

    cursor.execute("""CREATE TABLE km_processed_data (
        ConversationId varchar(255) NOT NULL PRIMARY KEY,
        StartTime varchar(255),
        EndTime varchar(255),
        Content varchar(max),
        summary varchar(max),
        satisfied varchar(255),
        sentiment varchar(255),
        keyphrases nvarchar(max),
        complaint varchar(255),
        topic varchar(255)
    )""")

    conn.commit()
    print("  ✓ Tabelas criadas: processed_data, processed_data_key_phrases, km_mined_topics, km_processed_data")

create_tables()

# ═══════════════════════════════════════════════════════════════════════════════
# PASSO 3: Carregar dados no SQL (processed_data + key_phrases)
# ═══════════════════════════════════════════════════════════════════════════════
def load_sql_data():
    print("\n── Passo 3: Carregar dados no SQL ─────────────────────────")
    with open(PROCESSED_DATA_FILE, "r", encoding="utf-8") as f:
        conversations = json.load(f)

    print(f"  → {len(conversations)} conversas carregadas do JSON")

    for conv in conversations:
        cursor.execute(
            """INSERT INTO processed_data
               (ConversationId, EndTime, StartTime, Content, summary, satisfied, sentiment, topic, key_phrases, complaint, mined_topic)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                conv["ConversationId"],
                conv.get("EndTime", ""),
                conv.get("StartTime", ""),
                conv.get("Content", ""),
                conv.get("summary", ""),
                conv.get("satisfied", ""),
                conv.get("sentiment", ""),
                conv.get("topic", ""),
                conv.get("key_phrases", ""),
                conv.get("complaint", ""),
                conv.get("mined_topic", "")
            )
        )
    conn.commit()
    print(f"  ✓ {len(conversations)} registros inseridos em processed_data")

    # Gerar key_phrases por conversa
    kp_count = 0
    for conv in conversations:
        kp_str = conv.get("key_phrases", "")
        if not kp_str:
            continue
        phrases = [p.strip() for p in kp_str.split(",") if p.strip()]
        for phrase in phrases:
            cursor.execute(
                """INSERT INTO processed_data_key_phrases
                   (ConversationId, key_phrase, sentiment, topic, StartTime)
                   VALUES (?,?,?,?,?)""",
                (
                    conv["ConversationId"],
                    phrase[:500],
                    conv.get("sentiment", ""),
                    conv.get("mined_topic", conv.get("topic", "")),
                    conv.get("StartTime", "")
                )
            )
            kp_count += 1
    conn.commit()
    print(f"  ✓ {kp_count} registros inseridos em processed_data_key_phrases")
    return conversations

conversations = load_sql_data()

# ═══════════════════════════════════════════════════════════════════════════════
# PASSO 4: Gerar embeddings e carregar no Azure Search
# ═══════════════════════════════════════════════════════════════════════════════
def clean_text(text):
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\.{2,}', '.', text)
    return text.strip()

def get_embedding(text):
    text = clean_text(text)
    try:
        resp = openai_client.embeddings.create(input=text, model=EMBEDDING_MODEL)
        return resp.data[0].embedding
    except Exception as e:
        print(f"  ! Erro embedding (retry em 30s): {e}")
        time.sleep(30)
        try:
            resp = openai_client.embeddings.create(input=text, model=EMBEDDING_MODEL)
            return resp.data[0].embedding
        except Exception as e2:
            print(f"  ! Falhou definitivamente: {e2}")
            return []

def chunk_content(text, max_tokens=1024):
    """Divide texto em chunks de ~1024 tokens (palavras)"""
    text = clean_text(text)
    sentences = text.split('. ')
    chunks, cur_chunk, cur_count = [], '', 0
    for sent in sentences:
        tokens = sent.split()
        if cur_count + len(tokens) <= max_tokens:
            cur_chunk = (cur_chunk + '. ' + sent).strip() if cur_chunk else sent
            cur_count += len(tokens)
        else:
            if cur_chunk:
                chunks.append(cur_chunk)
            cur_chunk, cur_count = sent, len(tokens)
    if cur_chunk:
        chunks.append(cur_chunk)
    return chunks if chunks else [text]

def load_search_data():
    print("\n── Passo 4: Gerar embeddings e carregar Azure Search ──────")
    all_docs = []
    for i, conv in enumerate(conversations):
        conv_id = conv["ConversationId"]
        content = conv.get("Content", "")
        if not content:
            continue
        chunks = chunk_content(content)
        for idx, chunk in enumerate(chunks, 1):
            chunk_id = f"{conv_id}_{str(idx).zfill(2)}"
            vec = get_embedding(chunk)
            all_docs.append({
                "id": chunk_id,
                "chunk_id": chunk_id,
                "content": chunk,
                "sourceurl": f"{conv_id}.json",
                "contentVector": vec
            })

        # Upload em lotes de 10 conversas
        if (i + 1) % 10 == 0 or i == len(conversations) - 1:
            if all_docs:
                batch = [{"@search.action": "upload", **doc} for doc in all_docs]
                try:
                    search_client.upload_documents(documents=batch)
                    print(f"  → {i+1}/{len(conversations)} conversas → {len(all_docs)} chunks no Search")
                except Exception as e:
                    print(f"  ! Erro upload Search: {e}")
                all_docs = []
            time.sleep(1)  # Evitar throttling

    print("  ✓ Todos os dados carregados no Azure Search")

load_search_data()

# ═══════════════════════════════════════════════════════════════════════════════
# PASSO 5: Minerar tópicos via GPT e popular km_mined_topics
# ═══════════════════════════════════════════════════════════════════════════════
def mine_topics():
    print("\n── Passo 5: Minerar tópicos (GPT-4o-mini) ─────────────────")

    # Coletar tópicos distintos dos dados
    cursor.execute("SELECT DISTINCT mined_topic FROM processed_data WHERE mined_topic IS NOT NULL AND mined_topic != ''")
    rows = cursor.fetchall()
    distinct_topics = [row[0] for row in rows if row[0]]
    print(f"  → {len(distinct_topics)} tópicos distintos em mined_topic: {distinct_topics}")

    # Usar os mined_topics já definidos nos dados como fonte de verdade
    # (os dados já foram gerados com tópicos corretos em PT-BR)
    topic_data = [
        {"label": "Seguro — Contratacao e Cancelamento",
         "description": "Atendimentos relacionados à contratação e cancelamento de seguros, incluindo seguro de vida, residencial e veicular"},
        {"label": "Seguro — Sinistros e Indenizacoes",
         "description": "Registro e acompanhamento de sinistros, perícias, indenizações e coberturas de apólices"},
        {"label": "Cartao de Credito — Fatura e Pagamento",
         "description": "Dúvidas e contestações sobre fatura, cobranças indevidas, anuidade e pagamentos"},
        {"label": "Cartao de Credito — Bloqueio e Contestacao",
         "description": "Bloqueio, desbloqueio, contestação de transações suspeitas e segunda via de cartão"},
        {"label": "Emprestimos — Simulacao e Contratacao",
         "description": "Solicitação de simulação, contratação de empréstimos pessoais e aprovação de crédito"},
        {"label": "Emprestimos — Renegociacao e Inadimplencia",
         "description": "Renegociação de dívidas, parcelamento em atraso, carência e quitação antecipada"},
        {"label": "Credito Especial — Credito Consignado",
         "description": "Crédito consignado, margem disponível, desconto em folha e consulta de contratos ativos"},
        {"label": "Credito Especial — Portabilidade de Credito",
         "description": "Portabilidade de crédito consignado, transferência de contrato entre instituições"},
        {"label": "Consorcio — Carta de Credito e Contemplacao",
         "description": "Contemplação por sorteio ou lance, liberação de carta de crédito e documentação"},
        {"label": "Consorcio — Duvidas sobre Grupo e Cota",
         "description": "Informações sobre grupo de consórcio, cota, assembleias e transferência de cota"},
    ]

    for t in topic_data:
        try:
            cursor.execute(
                "INSERT INTO km_mined_topics (label, description) VALUES (?,?)",
                (t["label"], t["description"])
            )
        except Exception as e:
            print(f"  ! Aviso inserindo topic '{t['label']}': {e}")
    conn.commit()
    print(f"  ✓ {len(topic_data)} tópicos inseridos em km_mined_topics")

    return [t["label"] for t in topic_data]

mined_topics = mine_topics()

# ═══════════════════════════════════════════════════════════════════════════════
# PASSO 6: Popular km_processed_data (view para RAG)
# ═══════════════════════════════════════════════════════════════════════════════
def populate_km_processed_data():
    print("\n── Passo 6: Popular km_processed_data (RAG view) ──────────")
    cursor.execute("""
        INSERT INTO km_processed_data
        (ConversationId, StartTime, EndTime, Content, summary, satisfied, sentiment, keyphrases, complaint, topic)
        SELECT ConversationId, StartTime, EndTime, Content, summary, satisfied, sentiment,
               key_phrases AS keyphrases, complaint, mined_topic AS topic
        FROM processed_data
    """)
    conn.commit()
    count = cursor.execute("SELECT COUNT(*) FROM km_processed_data").fetchone()[0]
    print(f"  ✓ {count} registros inseridos em km_processed_data")

populate_km_processed_data()

# ═══════════════════════════════════════════════════════════════════════════════
# PASSO 7: Verificação final
# ═══════════════════════════════════════════════════════════════════════════════
def verify():
    print("\n── Passo 7: Verificação Final ──────────────────────────────")

    for table in ["processed_data", "processed_data_key_phrases", "km_mined_topics", "km_processed_data"]:
        count = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  SQL [{table}]: {count} registros")

    try:
        result = search_client.search("", top=1, include_total_count=True)
        total = result.get_count()
        print(f"  Azure Search [{INDEX_NAME}]: {total} documentos")
    except Exception as e:
        print(f"  ! Erro ao contar docs no Search: {e}")

    print("\n✅ Carga completa com sucesso!")
    print(f"\n  Frontend: https://app-financeirax01.azurewebsites.net")
    print(f"  API docs: https://api-financeirax01.azurewebsites.net/docs")

verify()
conn.close()
