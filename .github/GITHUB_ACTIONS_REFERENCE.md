# GitHub Actions Reference

## Available Workflows

### 1. CI/CD Pipeline
**File**: `.github/workflows/ci-cd.yml`
**Triggers**: Push, PR to main/develop, manual
**Purpose**: Build, test, and validate code

**Jobs:**
- `test-api`: Test Python API (pytest, flake8, black)
- `test-frontend`: Test React app (npm test, ESLint)
- `validate-infrastructure`: Validate Bicep templates
- `docker-build`: Build Docker images
- `security-scan`: Trivy vulnerability scanning
- `build-status`: Overall build status check

### 2. CodeQL Security Scanning
**File**: `.github/workflows/codeql-analysis.yml`
**Triggers**: Push, PR, schedule (daily 2 AM UTC), manual
**Purpose**: Automated security vulnerability scanning

**Languages:**
- Python
- JavaScript/TypeScript

**Queries:**
- security-extended
- security-and-quality

### 3. Azure Deployment
**File**: `.github/workflows/azure-deploy.yml`
**Triggers**: Manual (workflow_dispatch), push to main
**Purpose**: Deploy infrastructure and application to Azure

**Jobs:**
- `validate`: Validate Bicep templates
- `deploy-infrastructure`: Deploy with azd
- `post-deployment-setup`: Load sample data
- `notify`: Send deployment summary

**Parameters:**
- `environment`: dev/staging/production
- `resource_group`: Azure resource group name

## Secrets Required

Add these to **Settings → Secrets and variables → Actions**:

| Secret Name | Description | How to Get |
|-------------|-------------|------------|
| `AZURE_CLIENT_ID` | Azure AD App Client ID | From Service Principal |
| `AZURE_TENANT_ID` | Azure AD Tenant ID | `az account show --query tenantId -o tsv` |
| `AZURE_SUBSCRIPTION_ID` | Azure Subscription ID | `az account show --query id -o tsv` |

## Manual Workflow Triggers

### Run CI/CD Pipeline
```bash
# Via GitHub UI
1. Go to Actions tab
2. Select "CI/CD Pipeline"
3. Click "Run workflow"
4. Select branch
5. Click "Run workflow"
```

### Run Azure Deployment
```bash
# Via GitHub UI
1. Go to Actions tab
2. Select "Deploy to Azure"
3. Click "Run workflow"
4. Select environment: dev/staging/production
5. Enter resource group name
6. Click "Run workflow"
```

### Run CodeQL Scan
```bash
# Via GitHub UI
1. Go to Actions tab
2. Select "CodeQL Security Scanning"
3. Click "Run workflow"
4. Select branch
5. Click "Run workflow"
```

## Workflow Status Badges

Add to your README.md:

```markdown
![CI/CD](https://github.com/YOUR_USERNAME/YOUR_REPO/actions/workflows/ci-cd.yml/badge.svg)
![CodeQL](https://github.com/YOUR_USERNAME/YOUR_REPO/actions/workflows/codeql-analysis.yml/badge.svg)
![Azure Deploy](https://github.com/YOUR_USERNAME/YOUR_REPO/actions/workflows/azure-deploy.yml/badge.svg)
```

## Common Workflow Commands

### Cancel Running Workflow
```bash
# Via GitHub CLI
gh run cancel <run-id>

# Or via GitHub UI
1. Go to Actions tab
2. Click on running workflow
3. Click "Cancel workflow"
```

### Re-run Failed Workflow
```bash
# Via GitHub CLI
gh run rerun <run-id>

# Or via GitHub UI
1. Go to Actions tab
2. Click on failed workflow
3. Click "Re-run jobs"
```

### View Workflow Logs
```bash
# Via GitHub CLI
gh run view <run-id> --log

# Or via GitHub UI
1. Go to Actions tab
2. Click on workflow run
3. Click on job name
4. View logs
```

## Troubleshooting

### Workflow Not Triggering

**Check:**
1. Workflow file is in `.github/workflows/`
2. YAML syntax is valid
3. Branch name matches trigger configuration
4. Actions are enabled in repo settings

### Authentication Errors

**Azure OIDC:**
```bash
# Verify federated credential
az ad app federated-credential list --id <APP_ID>

# Check subject format
"subject": "repo:USERNAME/REPO:ref:refs/heads/main"
```

### Permission Errors

**Check workflow permissions:**
1. Settings → Actions → General
2. Workflow permissions section
3. Ensure "Read and write permissions" is selected

### Timeout Issues

**Increase timeout:**
```yaml
jobs:
  my-job:
    timeout-minutes: 60  # Default is 360
```

## Best Practices

1. **Use matrix builds** for testing multiple versions
2. **Cache dependencies** to speed up builds
3. **Use environments** for deployment approval
4. **Set appropriate timeouts** to avoid hanging jobs
5. **Use job dependencies** to control workflow order
6. **Enable branch protection** to require status checks
7. **Review logs regularly** to catch issues early
8. **Use workflow artifacts** to share data between jobs

## Useful GitHub CLI Commands

```bash
# Install GitHub CLI
brew install gh  # macOS
# or visit: https://cli.github.com/

# Authenticate
gh auth login

# List workflows
gh workflow list

# View workflow runs
gh run list --workflow=ci-cd.yml

# Watch workflow run
gh run watch

# View workflow details
gh workflow view ci-cd.yml
```

## Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Workflow Syntax](https://docs.github.com/en/actions/reference/workflow-syntax-for-github-actions)
- [GitHub CLI Documentation](https://cli.github.com/manual/)
- [Azure Login Action](https://github.com/Azure/login)
