# Post-Deployment Setup Guide

## Overview

Due to Azure Policy restrictions that prevent shared key access on storage accounts, the standard deployment scripts cannot run automatically. This guide explains the manual setup process and the permanent fixes applied to the infrastructure.

## Permanent Changes Made

### 1. App Service Plan Upgraded to P1v2
**File:** `infra/main.bicep` (line ~1432)

**Change:**
```bicep
# Before:
skuName: enableScalability || enableRedundancy ? 'P1v3' : 'B3'

# After:
skuName: enableScalability || enableRedundancy ? 'P1v3' : 'P1v2'
```

**Reason:** Basic tier (B3) is too slow for AI workloads with vector search, embeddings, and agent processing. P1v2 provides:
- Faster CPU for AI operations
- 3.5GB RAM (vs 1.75GB)
- Always On feature (no cold starts)
- 5-15 second response times vs 30-60+ seconds

**Cost Impact:** ~$150/month vs ~$75/month for B3, but 3-4x better performance.

### 2. Storage Account Shared Key Access Disabled
**File:** `infra/main.bicep` (line ~1067)

**Status:** Already configured
```bicep
allowSharedKeyAccess: false
```

**Reason:** Complies with Azure Policy requiring Azure AD authentication only.

### 3. Deployment Scripts Commented Out
**File:** `infra/main.bicep` (lines 1358-1455)

**Status:** Already commented out
```bicep
/*
module uploadFiles '...'
module createIndex '...'
module createSqlUserAndRole '...'
*/
```

**Reason:** These scripts require shared key access which is blocked by Azure Policy. Replaced with post-deployment manual setup script.

## Post-Deployment Setup Process

After running `azd up`, execute the automated setup script:

### Prerequisites
- Azure CLI authenticated (`az login`)
- Python 3.11+ installed
- ODBC Driver 17 for SQL Server installed (script will note if missing)
- Run from repository root directory

### Quick Start

```bash
# After azd up completes successfully:
./infra/scripts/post-deployment-setup.sh <resource-group-name>

# Example:
./infra/scripts/post-deployment-setup.sh rg-ckmsa
```

### What the Script Does

1. **Discovers Resources** - Automatically finds Key Vault, SQL Server, Managed Identity, etc.
2. **Temporarily Opens Access** - Enables public access on Key Vault and SQL Server for data loading
3. **Assigns RBAC Roles** - Grants current user necessary permissions
4. **Installs Dependencies** - Installs Python packages
5. **Creates Search Index** - Sets up Azure AI Search with vector capabilities
6. **Loads Sample Data** - Uploads 112 conversation documents to search index
7. **Creates SQL User** - Adds managed identity to SQL database
8. **Loads SQL Data** - Populates 851 conversations and 2400 key phrases
9. **Creates Dashboard Tables** - Sets up km_processed_data and km_mined_topics
10. **Restores Security** - Disables public access and restores managed identity as admin

### Expected Output

```
==================================================
Post-Deployment Setup for CKM Solution
Resource Group: rg-ckmsa
==================================================

✅ Resource group found
📋 Discovering resources...
🔓 Step 1: Enabling Key Vault public access...
   ✅ Key Vault public access enabled
...
✅ Post-Deployment Setup Complete!
==================================================

🌐 Application URLs:
   UI:  https://app-xxxx.azurewebsites.net
   API: https://api-xxxx.azurewebsites.net

📊 Data Loaded:
   - Search Index: 112 documents
   - SQL Database: 851 conversations, 2400 key phrases

The application is ready to use!
```

### Time Required
- First run: ~5-10 minutes (includes package installation)
- Subsequent runs: ~3-5 minutes

## Manual Steps (If Script Fails)

If the automated script encounters issues, you can run steps manually:

### 1. Enable Access
```bash
# Enable Key Vault public access
az keyvault update --name <kv-name> --resource-group <rg-name> --public-network-access Enabled

# Enable SQL Server public access
az sql server update --name <sql-name> --resource-group <rg-name> --enable-public-network true
az sql server firewall-rule create --resource-group <rg-name> --server <sql-name> \
  --name AllowAll --start-ip-address 0.0.0.0 --end-ip-address 255.255.255.255
```

### 2. Install Dependencies
```bash
pip install -r infra/scripts/index_scripts/requirements.txt
```

### 3. Configure for Dev Mode
```bash
# Edit infra/scripts/index_scripts/azure_credential_utils.py
# Change: APP_ENV = 'prod' to APP_ENV = 'dev'
```

### 4. Run Setup Scripts
```bash
cd infra/scripts/index_scripts

# Create search index
python 01_create_search_index_manual.py <key-vault-name> <managed-identity-client-id>

# Load search data (use the Python script from the main script, or run manually)
```

### 5. Restore Security
```bash
# Disable Key Vault public access
az keyvault update --name <kv-name> --resource-group <rg-name> --public-network-access Disabled

# Restore managed identity as SQL admin
az sql server ad-admin create --resource-group <rg-name> --server <sql-name> \
  --display-name <managed-identity-name> --object-id <managed-identity-principal-id>
```

## Verification

### Check Search Index
```bash
# Test search functionality
python << 'EOF'
from azure.search.documents import SearchClient
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
client = SearchClient(endpoint="https://<search-name>.search.windows.net", 
                     index_name="call_transcripts_index", 
                     credential=credential)

results = client.search(search_text="lost phone", top=3)
print(f"Found {len(list(results))} results")
EOF
```

### Check SQL Data
```bash
# Verify table counts
az sql db query --server <sql-name> --database <db-name> --auth-mode ActiveDirectoryIntegrated \
  --query "SELECT COUNT(*) as count FROM km_processed_data"
```

### Test Application
1. Navigate to the Web UI URL
2. Sign in with Azure AD
3. Ask a question like: "Show me calls about lost phones"
4. Expected response time: 5-15 seconds (after initial cold start)

## Troubleshooting

### "Login failed for user" Error
- Ensure you've been added as SQL admin
- Wait 5-10 minutes for Azure AD propagation

### "Public network access is disabled" Error
- Run the enable access commands from Manual Steps section
- Verify firewall rules are in place

### "ODBC Driver not found" Error
```bash
# Debian/Ubuntu
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/debian/11/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql17
```

### Slow Response Times
- Check App Service Plan tier: should be P1v2 or higher
- Upgrade if needed:
  ```bash
  az appservice plan update --name <plan-name> --resource-group <rg-name> --sku P1V2
  ```
- First query after idle may take 30-60 seconds (cold start)

## Files Modified

- ✅ `infra/main.bicep` - Updated App Service Plan to P1v2
- ✅ `infra/main.bicep` - Deployment scripts commented out (already done)
- ✅ `infra/main.bicep` - Storage shared key access disabled (already done)
- ✅ `infra/scripts/post-deployment-setup.sh` - New automated setup script
- ✅ `POST_DEPLOYMENT_SETUP.md` - This documentation

## Next Deployment

When you redeploy the environment:

```bash
# 1. Deploy infrastructure
azd up

# 2. Run post-deployment setup
./infra/scripts/post-deployment-setup.sh <resource-group-name>

# 3. Application is ready!
```

The infrastructure changes (P1v2 tier, security settings) are permanent and will be applied automatically. Only the data loading requires the post-deployment script.

## Production Considerations

### Security
- The post-deployment script temporarily opens public access for data loading
- Access is automatically closed after setup completes
- In production, consider using Azure DevOps/GitHub Actions with self-hosted runners in the VNet

### Performance
- P1v2 is minimum recommended for production
- Consider P2v2 or P3v2 for higher traffic
- Enable autoscaling if needed

### Data Loading
- Sample data is for demonstration only
- Replace with your actual data in production
- Consider using Azure Data Factory or Synapse for large-scale data loading

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review deployment logs: `azd monitor`
3. Check application logs: `az webapp log tail --name <app-name> --resource-group <rg-name>`
