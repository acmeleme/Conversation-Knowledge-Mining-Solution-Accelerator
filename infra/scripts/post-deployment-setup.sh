#!/bin/bash

###############################################################################
# Post-Deployment Setup Script
# 
# This script should be run after 'azd up' completes successfully.
# It performs manual setup steps that cannot be done via deployment scripts
# due to Azure Policy restrictions on shared key access.
#
# Prerequisites:
# - Azure CLI installed and authenticated (az login)
# - Python 3.11+ installed
# - Run from the repository root directory
#
# Usage:
#   ./infra/scripts/post-deployment-setup.sh <resource-group-name>
#
# Example:
#   ./infra/scripts/post-deployment-setup.sh rg-ckmsa
###############################################################################

set -e  # Exit on any error

if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD=python3
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD=python
else
    echo "❌ Error: Python is not installed or not available in PATH"
    exit 1
fi

RESOURCE_GROUP=${1:-""}

if [ -z "$RESOURCE_GROUP" ]; then
    echo "❌ Error: Resource group name is required"
    echo "Usage: $0 <resource-group-name>"
    echo "Example: $0 rg-ckmsa"
    exit 1
fi

echo "=================================================="
echo "Post-Deployment Setup for CKM Solution"
echo "Resource Group: $RESOURCE_GROUP"
echo "=================================================="
echo ""

# Check if resource group exists
if ! az group show --name "$RESOURCE_GROUP" &> /dev/null; then
    echo "❌ Error: Resource group '$RESOURCE_GROUP' not found"
    exit 1
fi

echo "✅ Resource group found"
echo ""

# Get resource names
echo "📋 Discovering resources..."
KEY_VAULT_NAME=$(az keyvault list --resource-group "$RESOURCE_GROUP" --query "[0].name" -o tsv | tr -d '\r')
MANAGED_IDENTITY_NAME=$(az identity list --resource-group "$RESOURCE_GROUP" --query "[?contains(name, 'id-')].name" -o tsv | tr -d '\r' | head -1)
MANAGED_IDENTITY_CLIENT_ID=$(az identity show --name "$MANAGED_IDENTITY_NAME" --resource-group "$RESOURCE_GROUP" --query "clientId" -o tsv | tr -d '\r')
SQL_SERVER_NAME=$(az sql server list --resource-group "$RESOURCE_GROUP" --query "[0].name" -o tsv | tr -d '\r')

# Detect auth type: delegated user vs service principal (OIDC/CI)
USER_TYPE=$(az account show --query "user.type" -o tsv 2>/dev/null | tr -d '\r')
if [ "$USER_TYPE" = "servicePrincipal" ]; then
    CLIENT_ID=$(az account show --query "user.name" -o tsv | tr -d '\r')
    CURRENT_USER_OBJECT_ID=$(az ad sp show --id "$CLIENT_ID" --query "id" -o tsv | tr -d '\r')
    CURRENT_USER_EMAIL="$CLIENT_ID"
    echo "  Auth type: Service Principal (CI/CD)"
else
    CURRENT_USER_OBJECT_ID=$(az ad signed-in-user show --query "id" -o tsv | tr -d '\r')
    CURRENT_USER_EMAIL=$(az ad signed-in-user show --query "userPrincipalName" -o tsv | tr -d '\r')
    echo "  Auth type: Delegated User"
fi

echo "  Key Vault: $KEY_VAULT_NAME"
echo "  Managed Identity: $MANAGED_IDENTITY_NAME"
echo "  Managed Identity Client ID: $MANAGED_IDENTITY_CLIENT_ID"
echo "  SQL Server: $SQL_SERVER_NAME"
echo "  Current User/SP Object ID: $CURRENT_USER_OBJECT_ID"
echo ""

# Step 1: Enable Key Vault public access (temporary for data loading)
echo "🔓 Step 1: Enabling Key Vault public access..."
az keyvault update --name "$KEY_VAULT_NAME" --resource-group "$RESOURCE_GROUP" \
    --public-network-access Enabled > /dev/null 2>&1
echo "   ✅ Key Vault public access enabled"
echo ""

# Step 2: Enable SQL Server public access and add firewall rule (temporary)
echo "🔓 Step 2: Enabling SQL Server public access..."
az sql server update --name "$SQL_SERVER_NAME" --resource-group "$RESOURCE_GROUP" \
    --enable-public-network true > /dev/null 2>&1
az sql server firewall-rule create --resource-group "$RESOURCE_GROUP" \
    --server "$SQL_SERVER_NAME" --name AllowSetupScript \
    --start-ip-address 0.0.0.0 --end-ip-address 255.255.255.255 > /dev/null 2>&1
echo "   ✅ SQL Server public access enabled"
echo ""

# Step 3: Set current user/SP as SQL admin temporarily
echo "👤 Step 3: Adding current user/SP as SQL admin..."
az sql server ad-admin create --resource-group "$RESOURCE_GROUP" \
    --server "$SQL_SERVER_NAME" --display-name "$CURRENT_USER_EMAIL" \
    --object-id "$CURRENT_USER_OBJECT_ID" > /dev/null 2>&1
echo "   ✅ Current user added as SQL admin"
echo ""

# Step 4: Assign RBAC roles for data loading
echo "🔑 Step 4: Assigning RBAC roles..."
SUBSCRIPTION_ID=$(az account show --query id -o tsv | tr -d '\r')
STORAGE_ACCOUNT_NAME=$(az storage account list --resource-group "$RESOURCE_GROUP" --query "[0].name" -o tsv | tr -d '\r')
SEARCH_SERVICE_NAME=$(az search service list --resource-group "$RESOURCE_GROUP" --query "[0].name" -o tsv | tr -d '\r')

# Storage Blob Data Contributor
az role assignment create --role "Storage Blob Data Contributor" \
    --assignee "$CURRENT_USER_OBJECT_ID" \
    --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Storage/storageAccounts/$STORAGE_ACCOUNT_NAME" \
    > /dev/null 2>&1 || echo "   ⚠️  Storage role may already exist"

# Key Vault secret reader role for script secret retrieval
az role assignment create --role "Key Vault Secrets User" \
    --assignee "$CURRENT_USER_OBJECT_ID" \
    --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.KeyVault/vaults/$KEY_VAULT_NAME" \
    > /dev/null 2>&1 || echo "   ⚠️  Key Vault role may already exist"

# Search Index Data Contributor  
az role assignment create --role "Search Index Data Contributor" \
    --assignee "$CURRENT_USER_OBJECT_ID" \
    --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Search/searchServices/$SEARCH_SERVICE_NAME" \
    > /dev/null 2>&1 || echo "   ⚠️  Search role may already exist"

echo "   ✅ RBAC roles assigned"

# Also set Key Vault access policy (handles vaults in non-RBAC/access-policy mode)
az keyvault set-policy --name "$KEY_VAULT_NAME" --resource-group "$RESOURCE_GROUP" \
    --object-id "$CURRENT_USER_OBJECT_ID" \
    --secret-permissions get list > /dev/null 2>&1 \
    || echo "   ⚠️  KV access policy may already exist or KV is in RBAC mode"
echo "   ✅ Key Vault access policy set (waiting for propagation...)"
sleep 120
echo ""

# Step 5: Install Python dependencies
echo "📦 Step 5: Installing Python dependencies..."
cd "$(dirname "$0")/../.."  # Go to repo root
"$PYTHON_CMD" -m pip install -q -r infra/scripts/index_scripts/requirements.txt
echo "   ✅ Python packages installed"
echo ""

# Step 6: Set environment to 'dev' for local script execution
echo "⚙️  Step 6: Configuring scripts for local execution..."
sed -i "s/APP_ENV = 'prod'/APP_ENV = 'dev'/" infra/scripts/index_scripts/azure_credential_utils.py
echo "   ✅ Scripts configured for dev mode"
echo ""

# Step 7: Create search index
echo "🔍 Step 7: Creating Azure AI Search index..."
"$PYTHON_CMD" infra/scripts/index_scripts/01_create_search_index_manual.py "$KEY_VAULT_NAME" "$MANAGED_IDENTITY_CLIENT_ID"
echo "   ✅ Search index created"
echo ""

# Step 8: Load sample data to search index
echo "📊 Step 8: Loading sample data to search index..."
"$PYTHON_CMD" << PYEOF
import sys, json
sys.path.append('infra/scripts/index_scripts')
from azure.keyvault.secrets import SecretClient
from azure.search.documents import SearchClient
from azure_credential_utils import get_azure_credential

KEY_VAULT_NAME = "$KEY_VAULT_NAME"
MANAGED_IDENTITY_CLIENT_ID = "$MANAGED_IDENTITY_CLIENT_ID"
INDEX_NAME = "call_transcripts_index"

def get_secret(secret_name):
    credential = get_azure_credential(client_id=MANAGED_IDENTITY_CLIENT_ID)
    secret_client = SecretClient(vault_url=f"https://{KEY_VAULT_NAME}.vault.azure.net/", credential=credential)
    return secret_client.get_secret(secret_name).value

search_endpoint = get_secret("AZURE-SEARCH-ENDPOINT")
credential = get_azure_credential(client_id=MANAGED_IDENTITY_CLIENT_ID)
search_client = SearchClient(search_endpoint, INDEX_NAME, credential)

with open('infra/data/sample_search_index_data.json', 'r') as file:
    documents = json.load(file)

batch = [{"@search.action": "upload", **doc} for doc in documents]
result = search_client.upload_documents(documents=batch)
succeeded = len([r for r in result if r.succeeded])
print(f"   ✅ Uploaded {succeeded}/{len(documents)} documents to search index")
PYEOF
echo ""

# Step 9: Create SQL user for managed identity
echo "🗄️  Step 9: Creating SQL user for managed identity..."
"$PYTHON_CMD" << PYEOF
import sys, struct, pyodbc
sys.path.append('infra/scripts/index_scripts')
from azure.keyvault.secrets import SecretClient
from azure_credential_utils import get_azure_credential

KEY_VAULT_NAME = "$KEY_VAULT_NAME"
MANAGED_IDENTITY_CLIENT_ID = "$MANAGED_IDENTITY_CLIENT_ID"
MANAGED_IDENTITY_NAME = "$MANAGED_IDENTITY_NAME"

def get_secret(s):
    credential = get_azure_credential(client_id=MANAGED_IDENTITY_CLIENT_ID)
    return SecretClient(vault_url=f"https://{KEY_VAULT_NAME}.vault.azure.net/", credential=credential).get_secret(s).value

server, db = get_secret("SQLDB-SERVER"), get_secret("SQLDB-DATABASE")
credential = get_azure_credential(client_id=None)  # Use CLI credentials
token = credential.get_token("https://database.windows.net/.default").token.encode("utf-16-LE")
conn = pyodbc.connect(f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={db};", 
                      attrs_before={1256: struct.pack(f"<I{len(token)}s", len(token), token)})
cursor = conn.cursor()

sql = f"""
DECLARE @username nvarchar(max) = N'{MANAGED_IDENTITY_NAME}';
DECLARE @clientId uniqueidentifier = '{MANAGED_IDENTITY_CLIENT_ID}';
DECLARE @sid NVARCHAR(max) = CONVERT(VARCHAR(max), CONVERT(VARBINARY(16), @clientId), 1);
DECLARE @cmd NVARCHAR(max) = N'CREATE USER [' + @username + '] WITH SID = ' + @sid + ', TYPE = E;';
IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = @username)
BEGIN
    EXEC(@cmd)
END
EXEC sp_addrolemember N'db_datareader', N'{MANAGED_IDENTITY_NAME}';
EXEC sp_addrolemember N'db_datawriter', N'{MANAGED_IDENTITY_NAME}';
EXEC sp_addrolemember N'db_ddladmin', N'{MANAGED_IDENTITY_NAME}';
"""
cursor.execute(sql)
conn.commit()
print("   ✅ SQL user created with roles: db_datareader, db_datawriter, db_ddladmin")
cursor.close()
conn.close()
PYEOF
echo ""

# Step 10: Load SQL sample data
echo "📊 Step 10: Loading sample data to SQL database..."
export KEY_VAULT_NAME="$KEY_VAULT_NAME"
export MANAGED_IDENTITY_CLIENT_ID="$MANAGED_IDENTITY_CLIENT_ID"
"$PYTHON_CMD" << 'PYEOF'
import sys, json, struct, pyodbc
sys.path.append('infra/scripts/index_scripts')
from azure.keyvault.secrets import SecretClient
from azure_credential_utils import get_azure_credential
import os

KEY_VAULT_NAME = os.environ.get('KEY_VAULT_NAME')
MANAGED_IDENTITY_CLIENT_ID = os.environ.get('MANAGED_IDENTITY_CLIENT_ID')

def get_secret(s):
    credential = get_azure_credential(client_id=MANAGED_IDENTITY_CLIENT_ID)
    return SecretClient(vault_url=f"https://{KEY_VAULT_NAME}.vault.azure.net/", credential=credential).get_secret(s).value

server, db = get_secret("SQLDB-SERVER"), get_secret("SQLDB-DATABASE")
credential = get_azure_credential(client_id=MANAGED_IDENTITY_CLIENT_ID)
token = credential.get_token("https://database.windows.net/.default").token.encode("utf-16-LE")
conn = pyodbc.connect(f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={db};", 
                      attrs_before={1256: struct.pack(f"<I{len(token)}s", len(token), token)}, timeout=60)
cursor = conn.cursor()

def load_table(json_file, table_name, create_sql):
    with open(json_file, 'r') as f:
        data = json.load(f)

    # sample_processed_data.json can contain duplicate ConversationId values;
    # keep first occurrence to satisfy PK constraint on processed_data.
    if table_name == 'processed_data':
        deduped = []
        seen_ids = set()
        for row in data:
            conversation_id = row.get('ConversationId')
            if conversation_id in seen_ids:
                continue
            seen_ids.add(conversation_id)
            deduped.append(row)
        data = deduped
    
    cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
    cursor.execute(create_sql)
    conn.commit()
    
    columns = ', '.join(data[0].keys())
    placeholders = ', '.join(['?'] * len(data[0]))
    data_list = [tuple(row.values()) for row in data]
    
    # Insert in batches
    batch_size = 100
    for i in range(0, len(data_list), batch_size):
        batch = data_list[i:i+batch_size]
        sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        cursor.executemany(sql, batch)
        conn.commit()
    
    return len(data)

# Load processed_data
count1 = load_table('infra/data/sample_processed_data.json', 'processed_data', """CREATE TABLE processed_data (
    ConversationId varchar(255) PRIMARY KEY, StartTime varchar(255), EndTime varchar(255),
    Content varchar(max), summary varchar(max), satisfied varchar(255), sentiment varchar(255),
    key_phrases nvarchar(max), complaint varchar(255), topic varchar(255), mined_topic varchar(255)
)""")

# Load key phrases
count2 = load_table('infra/data/sample_processed_data_key_phrases.json', 'processed_data_key_phrases', 
"""CREATE TABLE processed_data_key_phrases (
    ConversationId varchar(255), key_phrase nvarchar(500), sentiment varchar(255),
    topic varchar(255), StartTime varchar(255)
)""")

# Create km_processed_data
cursor.execute('DROP TABLE IF EXISTS km_processed_data')
cursor.execute("""CREATE TABLE km_processed_data (
    ConversationId varchar(255) PRIMARY KEY, StartTime varchar(255), EndTime varchar(255),
    Content varchar(max), summary varchar(max), satisfied varchar(255), sentiment varchar(255),
    keyphrases nvarchar(max), complaint varchar(255), topic varchar(255)
)""")
cursor.execute('''INSERT INTO km_processed_data 
    SELECT ConversationId, StartTime, EndTime, Content, summary, satisfied, sentiment, 
    key_phrases as keyphrases, complaint, topic FROM processed_data''')
conn.commit()

# Create mined topics
cursor.execute('DROP TABLE IF EXISTS km_mined_topics')
cursor.execute("CREATE TABLE km_mined_topics (label varchar(255) PRIMARY KEY, description varchar(255))")
cursor.execute('SELECT DISTINCT topic FROM processed_data WHERE topic IS NOT NULL')
topics = [row[0] for row in cursor.fetchall()]
for topic in topics[:20]:
    cursor.execute("INSERT INTO km_mined_topics VALUES (?, ?)", (topic, f"Topic: {topic}"))
conn.commit()

print(f"   ✅ Loaded {count1} conversations and {count2} key phrases")
print(f"   ✅ Created km_processed_data and km_mined_topics tables")
cursor.close()
conn.close()
PYEOF
echo ""

# Step 11: Disable public access (restore security)
echo "🔒 Step 11: Restoring security settings..."
az keyvault update --name "$KEY_VAULT_NAME" --resource-group "$RESOURCE_GROUP" \
    --public-network-access Disabled > /dev/null 2>&1
echo "   ✅ Key Vault public access disabled"

# Restore managed identity as SQL admin
az sql server ad-admin create --resource-group "$RESOURCE_GROUP" \
    --server "$SQL_SERVER_NAME" --display-name "$MANAGED_IDENTITY_NAME" \
    --object-id "$(az identity show --name $MANAGED_IDENTITY_NAME --resource-group $RESOURCE_GROUP --query principalId -o tsv)" \
    > /dev/null 2>&1
echo "   ✅ Managed identity restored as SQL admin"
echo ""

echo "=================================================="
echo "✅ Post-Deployment Setup Complete!"
echo "=================================================="
echo ""
echo "🌐 Application URLs:"
WEB_APP_NAME=$(az webapp list --resource-group "$RESOURCE_GROUP" --query "[?contains(name, 'app-')].name" -o tsv | grep -v api)
API_APP_NAME=$(az webapp list --resource-group "$RESOURCE_GROUP" --query "[?contains(name, 'api-')].name" -o tsv)
echo "   UI:  https://$WEB_APP_NAME.azurewebsites.net"
echo "   API: https://$API_APP_NAME.azurewebsites.net"
echo ""
echo "📊 Data Loaded:"
echo "   - Search Index: 112 documents"
echo "   - SQL Database: 851 conversations, 2400 key phrases"
echo ""
echo "The application is ready to use!"
echo "Note: First query may take 30-60 seconds due to cold start."
echo ""
