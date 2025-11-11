# GitHub Setup Guide: GHAS & CI/CD

This guide will help you set up GitHub Advanced Security (GHAS) and CI/CD pipelines for the Conversation Knowledge Mining Solution Accelerator.

## Prerequisites

- GitHub account with **GitHub Advanced Security** enabled (available for GitHub Enterprise, public repos, or with GHAS license)
- Azure subscription with appropriate permissions
- Azure CLI installed locally
- Git installed locally

## Step 1: Create GitHub Repository

### Option A: Create a new repository on GitHub

1. Go to https://github.com/new
2. Enter repository name: `conversation-knowledge-mining-solution`
3. Choose visibility:
   - **Public**: GHAS features are free
   - **Private**: Requires GitHub Advanced Security license
4. **Do not** initialize with README (we already have one)
5. Click "Create repository"

### Option B: Push to existing repository

If you already have a repository, continue to Step 2.

## Step 2: Push Code to GitHub

```bash
# Navigate to the project directory
cd /workspaces/Conversation-Knowledge-Mining-Solution-Accelerator

# Initialize git if not already done
git init

# Add remote (replace with your GitHub username/org)
git remote add origin https://github.com/YOUR_USERNAME/conversation-knowledge-mining-solution.git

# Check current branch name
git branch

# Rename to main if needed
git branch -M main

# Stage all files
git add .

# Commit
git commit -m "Initial commit with GHAS and CI/CD configuration"

# Push to GitHub
git push -u origin main
```

## Step 3: Enable GitHub Advanced Security Features

### A. Enable Code Scanning (CodeQL)

1. Go to your repository on GitHub
2. Click **Settings** → **Code security and analysis**
3. Under "Code scanning":
   - Click **Set up** → **Default** (recommended for most projects)
   - Or use the CodeQL workflow we created: `.github/workflows/codeql-analysis.yml`
4. CodeQL will automatically scan your code on:
   - Every push to main/develop
   - Every pull request
   - Daily at 2 AM UTC (scheduled scan)

### B. Enable Dependabot Security Updates

1. In **Settings** → **Code security and analysis**
2. Enable **Dependabot alerts**
3. Enable **Dependabot security updates**
4. Enable **Dependabot version updates** (already configured in `.github/dependabot.yml`)

### C. Enable Secret Scanning

1. In **Settings** → **Code security and analysis**
2. Enable **Secret scanning**
3. Enable **Push protection** (prevents accidentally pushing secrets)

### D. Enable Dependency Graph

1. In **Settings** → **Code security and analysis**
2. Enable **Dependency graph** (should be enabled by default)

## Step 4: Configure Azure Credentials for CI/CD

### Set up Azure OIDC (Recommended - No secrets!)

```bash
# Login to Azure
az login

# Get subscription ID
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
echo "Subscription ID: $SUBSCRIPTION_ID"

# Create an Azure AD Application
APP_NAME="github-actions-ckm"
az ad app create --display-name "$APP_NAME"

# Get the Application ID
APP_ID=$(az ad app list --display-name "$APP_NAME" --query "[0].appId" -o tsv)
echo "Application (Client) ID: $APP_ID"

# Create a Service Principal
az ad sp create --id $APP_ID

# Get the Service Principal Object ID
SP_OBJECT_ID=$(az ad sp list --display-name "$APP_NAME" --query "[0].id" -o tsv)
echo "Service Principal Object ID: $SP_OBJECT_ID"

# Assign Contributor role to the Service Principal
az role assignment create \
  --role "Contributor" \
  --assignee $APP_ID \
  --scope "/subscriptions/$SUBSCRIPTION_ID"

# Create federated credentials for GitHub Actions
# Replace YOUR_GITHUB_USERNAME and YOUR_REPO_NAME
GITHUB_REPO="YOUR_GITHUB_USERNAME/YOUR_REPO_NAME"

az ad app federated-credential create \
  --id $APP_ID \
  --parameters "{
    \"name\": \"github-actions-main\",
    \"issuer\": \"https://token.actions.githubusercontent.com\",
    \"subject\": \"repo:${GITHUB_REPO}:ref:refs/heads/main\",
    \"audiences\": [\"api://AzureADTokenExchange\"]
  }"

# Get Tenant ID
TENANT_ID=$(az account show --query tenantId -o tsv)
echo "Tenant ID: $TENANT_ID"

# Print summary
echo "========================================"
echo "Add these secrets to GitHub:"
echo "========================================"
echo "AZURE_CLIENT_ID: $APP_ID"
echo "AZURE_TENANT_ID: $TENANT_ID"
echo "AZURE_SUBSCRIPTION_ID: $SUBSCRIPTION_ID"
```

### Add Secrets to GitHub

1. Go to your repository on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret** and add:
   - `AZURE_CLIENT_ID`: (from above)
   - `AZURE_TENANT_ID`: (from above)
   - `AZURE_SUBSCRIPTION_ID`: (from above)

### Create Environments (Optional but Recommended)

1. Go to **Settings** → **Environments**
2. Create environments:
   - `dev`
   - `staging`
   - `production`
3. For each environment:
   - Add **Required reviewers** (for production)
   - Add **Wait timer** (optional delay before deployment)
   - Add **Deployment branches** rules

## Step 5: Update Dependabot Configuration

Edit `.github/dependabot.yml` and replace `your-github-username` with your actual GitHub username:

```yaml
reviewers:
  - "YOUR_GITHUB_USERNAME"  # Replace this
```

## Step 6: Test Your Setup

### Test CI/CD Pipeline

1. Make a small change to any file
2. Commit and push:
   ```bash
   git add .
   git commit -m "test: trigger CI/CD pipeline"
   git push
   ```
3. Go to **Actions** tab on GitHub
4. Watch the "CI/CD Pipeline" workflow run

### Test CodeQL Scanning

1. CodeQL will run automatically on your first push
2. Go to **Security** → **Code scanning**
3. Review any findings

### Test Dependabot

1. Go to **Security** → **Dependabot**
2. Dependabot will start checking for updates weekly
3. PRs will be created automatically for updates

### Test Azure Deployment

1. Go to **Actions** tab
2. Click **Deploy to Azure** workflow
3. Click **Run workflow**
4. Select environment and resource group
5. Click **Run workflow**

## Step 7: Review Security Posture

### Security Overview Dashboard

1. Go to **Security** → **Overview**
2. Review:
   - **Dependabot alerts**: Vulnerable dependencies
   - **Code scanning alerts**: Security vulnerabilities in code
   - **Secret scanning alerts**: Exposed secrets

### Enable Additional Features

1. **Security policy**: Create `SECURITY.md` with vulnerability reporting instructions
2. **Branch protection**: Protect `main` branch
   - Go to **Settings** → **Branches**
   - Add rule for `main`:
     - ✅ Require pull request reviews
     - ✅ Require status checks to pass (select CI/CD jobs)
     - ✅ Require CodeQL to pass
     - ✅ Include administrators

## Step 8: Configure Notifications

1. Go to **Settings** → **Notifications**
2. Configure notifications for:
   - Dependabot alerts
   - Security alerts
   - Failed workflow runs

## Step 9: Set Up Code Owners (Optional)

Create `.github/CODEOWNERS`:

```
# Global owners
* @YOUR_GITHUB_USERNAME

# Infrastructure code
/infra/ @YOUR_GITHUB_USERNAME

# Python API
/src/api/ @YOUR_GITHUB_USERNAME

# React frontend
/src/App/ @YOUR_GITHUB_USERNAME

# CI/CD workflows
/.github/workflows/ @YOUR_GITHUB_USERNAME
```

## GitHub Advanced Security Features Summary

| Feature | Status | Description |
|---------|--------|-------------|
| **CodeQL Scanning** | ✅ Configured | Automated code scanning for vulnerabilities |
| **Dependabot Alerts** | ✅ Configured | Security alerts for vulnerable dependencies |
| **Dependabot Updates** | ✅ Configured | Automated PRs for dependency updates |
| **Secret Scanning** | ⚙️ Manual | Enable in Settings → Security |
| **Security Overview** | ✅ Available | Central dashboard for all security findings |
| **CI/CD Pipeline** | ✅ Configured | Automated build, test, and deploy |
| **Azure Deployment** | ✅ Configured | Automated infrastructure and app deployment |

## CI/CD Workflows

### 1. **CI/CD Pipeline** (`.github/workflows/ci-cd.yml`)
- **Triggers**: Push, PR to main/develop
- **Jobs**:
  - Test Python API (pytest, flake8, black)
  - Test React frontend (npm test, ESLint)
  - Validate Bicep templates
  - Build Docker images
  - Security scan with Trivy

### 2. **CodeQL Analysis** (`.github/workflows/codeql-analysis.yml`)
- **Triggers**: Push, PR, schedule (daily)
- **Languages**: Python, JavaScript/TypeScript
- **Queries**: security-extended, security-and-quality

### 3. **Azure Deploy** (`.github/workflows/azure-deploy.yml`)
- **Triggers**: Manual (workflow_dispatch), push to main
- **Jobs**:
  - Validate infrastructure
  - Deploy with azd
  - Run post-deployment setup
  - Verify deployment

## Troubleshooting

### CodeQL Not Running

- Check that `.github/workflows/codeql-analysis.yml` exists
- Verify workflow permissions in Settings → Actions → General
- Ensure CodeQL is enabled in Settings → Code security

### Dependabot PRs Not Created

- Check `.github/dependabot.yml` configuration
- Verify Dependabot is enabled in Settings
- Check Dependabot logs in Insights → Dependency graph → Dependabot

### Azure Deployment Failing

- Verify Azure credentials are correct
- Check federated credential subject matches your repo
- Review workflow run logs for specific errors
- Ensure Service Principal has Contributor role

### Secret Scanning Alerts

- Review alerts in Security → Secret scanning
- Rotate exposed secrets immediately
- Enable push protection to prevent future leaks

## Best Practices

1. **Never commit secrets** - Use Azure Key Vault and managed identities
2. **Review Dependabot PRs** - Don't auto-merge without testing
3. **Fix CodeQL findings** - Address security vulnerabilities promptly
4. **Use branch protection** - Require reviews and status checks
5. **Monitor Security dashboard** - Check regularly for new alerts
6. **Keep dependencies updated** - Merge Dependabot PRs weekly
7. **Use environments** - Separate dev, staging, production
8. **Enable notifications** - Stay informed of security issues

## Resources

- [GitHub Advanced Security Documentation](https://docs.github.com/en/code-security)
- [CodeQL Documentation](https://codeql.github.com/docs/)
- [Dependabot Documentation](https://docs.github.com/en/code-security/dependabot)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Azure OIDC with GitHub Actions](https://docs.microsoft.com/en-us/azure/developer/github/connect-from-azure)

---

## Quick Reference Commands

```bash
# Check for security issues locally
npm audit                          # Frontend vulnerabilities
pip-audit                          # Python vulnerabilities (install: pip install pip-audit)
trivy fs .                         # Scan filesystem for vulnerabilities

# Run tests locally
cd src/api && pytest               # Python tests
cd src/App && npm test             # React tests

# Validate Bicep
cd infra && bicep build main.bicep

# Deploy to Azure
azd up --no-prompt
bash infra/scripts/post-deployment-setup.sh rg-ckmsa
```

---

**🎉 Congratulations!** Your repository is now set up with GitHub Advanced Security and automated CI/CD pipelines!
