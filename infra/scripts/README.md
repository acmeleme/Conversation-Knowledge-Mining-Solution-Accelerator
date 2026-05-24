# Infra Scripts — Azure Entra ID RBAC

## Objetivo
Automatizar a configuração de Azure Entra ID RBAC para a solução Conversation Knowledge Mining, incluindo:
- App Registration `ckm-callcenter-app`
- App Roles `callcenter` e `faturamento`
- Service Principal
- Usuários de teste
- Configuração de Easy Auth no App Service

## Ordem de execução recomendada
1. **PowerShell (Windows)**
   ```powershell
   .\setup-entra-id-rbac.ps1
   ```
2. **Bash (Linux/macOS)**
   ```bash
   ./setup-entra-id-rbac.sh
   ```
3. **Configurar Easy Auth**
   ```powershell
   .\configure-easy-auth.ps1
   ```
4. **Validar usuários e roles**
   - Consulte `test-users-setup.md`

> Execute apenas **um** dos scripts de setup (`.ps1` ou `.sh`). Ambos produzem `infra/scripts/.rbac-output.json`.

## Scripts disponíveis
### `setup-entra-id-rbac.ps1`
Cria ou reaproveita a App Registration `ckm-callcenter-app`, adiciona App Roles, cria o Service Principal, cria usuários de teste e grava o resultado em `.rbac-output.json`.

### `setup-entra-id-rbac.sh`
Versão Bash para Linux/macOS com o mesmo fluxo funcional do script PowerShell.

### `configure-easy-auth.ps1`
Localiza os App Services no resource group `rg-callcenter-100`, habilita App Service Authentication com Azure AD, configura Token Store e atualiza redirect URIs na App Registration.

### `test-users-setup.md`
Checklist operacional para validar criação de usuários, atribuição de roles e inspeção de claims JWT.

## Saída gerada
O arquivo `infra/scripts/.rbac-output.json` inclui:
- `clientId`
- `tenantId`
- `tenantDomain`
- `servicePrincipalObjectId`
- IDs das App Roles
- usuários de teste e senha temporária (quando o usuário é criado pelo script)

## Pré-requisitos
- Azure CLI autenticado com permissão para Microsoft Entra ID e App Service.
- Permissão para criar App Registration, Service Principal, usuários e atribuições de App Roles.
- Permissão para alterar Authentication no App Service.
- No Linux/macOS, `python3` disponível para manipular JSON no script Bash.

## Observações
- O script trata `faturamento` como role de acesso mais ampla; a aplicação deve aceitar `faturamento` nos mesmos fluxos liberados para `callcenter`.
- Comandos `az rest` são tenant-scoped e dependem do contexto definido por `az account set --subscription a2ec8402-d75b-419c-b71d-7558309c50dc`.
