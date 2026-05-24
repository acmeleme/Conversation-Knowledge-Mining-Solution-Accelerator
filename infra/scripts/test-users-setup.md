# Verificação manual dos usuários de teste e RBAC

## Pré-requisitos
- Azure CLI autenticado no tenant correto.
- App Registration `ckm-callcenter-app` criada.
- Arquivo `infra/scripts/.rbac-output.json` gerado pelo script de setup.
- Easy Auth configurado no App Service.

## 1. Validar criação dos usuários
1. Abra o portal Azure.
2. Vá para **Microsoft Entra ID** > **Users**.
3. Pesquise pelos usuários:
   - `operador-callcenter@<tenant>.onmicrosoft.com`
   - `financeiro-faturamento@<tenant>.onmicrosoft.com`
4. Confirme que ambos estão habilitados.
5. Se o script tiver criado os usuários, anote a senha temporária exibida em `.rbac-output.json` e force a troca no primeiro login.

## 2. Validar App Roles no portal
1. Vá para **Microsoft Entra ID** > **App registrations** > `ckm-callcenter-app`.
2. Abra **App roles**.
3. Confirme a existência das roles:
   - `callcenter` — **Call Center Operator**
   - `faturamento` — **Financeiro/Faturamento**
4. Verifique as descrições:
   - `Acesso a todos os tópicos exceto Billing and Payment Issues`
   - `Acesso completo incluindo Billing and Payment Issues`

## 3. Atribuir App Roles manualmente no Azure Portal
> Use este fluxo se precisar corrigir ou recriar as atribuições feitas pelo script.

1. Vá para **Microsoft Entra ID** > **Enterprise applications**.
2. Abra a aplicação empresarial correspondente a `ckm-callcenter-app`.
3. Selecione **Users and groups** > **Add user/group**.
4. Escolha o usuário desejado.
5. Em **Select role**, escolha:
   - `Call Center Operator` para o operador.
   - `Financeiro/Faturamento` para o usuário financeiro.
6. Clique em **Assign**.

## 4. Validar roles no JWT / Easy Auth
### Opção A — `/.auth/me`
1. Faça login no App Service usando um dos usuários de teste.
2. Acesse `https://<app>.azurewebsites.net/.auth/me`.
3. Procure a claim `roles` no token retornado.
4. Resultado esperado:
   - Operador: `roles` contém `callcenter`
   - Financeiro: `roles` contém `faturamento`

### Opção B — Ferramentas do navegador
1. Faça login no App Service.
2. Abra **Developer Tools** > **Network**.
3. Inspecione a resposta de `/.auth/me` ou o token enviado ao frontend.
4. Decodifique o JWT em uma ferramenta interna/aprovada e valide a claim `roles`.

## 5. Checklist de validação RBAC
- [ ] `operador-callcenter` acessa tópicos gerais.
- [ ] `operador-callcenter` **não** acessa `Billing and Payment Issues`.
- [ ] `financeiro-faturamento` acessa tópicos gerais.
- [ ] `financeiro-faturamento` acessa `Billing and Payment Issues`.
- [ ] A claim `roles` aparece no token JWT.
- [ ] O App Service redireciona corretamente para login Microsoft.
- [ ] O logout retorna para a aplicação sem erro.

## 6. Troubleshooting rápido
- Se a role não aparecer no token, revalide a atribuição em **Enterprise applications**.
- Se o login falhar, confirme os redirect URIs `https://<app>.azurewebsites.net/.auth/login/aad/callback` na App Registration.
- Se houver cache de sessão, encerre a sessão e faça novo login após alterar roles.
