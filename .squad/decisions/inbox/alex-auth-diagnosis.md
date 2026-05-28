# Alex Auth Diagnosis — /.auth/me retorna 401 com body vazio

**Data:** 2026-05-28  
**Autor:** Alex (fullstack)  
**Status:** Resolvido — aguarda rebuild e deploy da imagem Docker

---

## Problema

O componente `App` em `src/App/src/App.tsx` exibia "Dev Local" em produção mesmo com o usuário autenticado no Entra ID. O síntoma persistia após o deploy do fix anterior (snake_case).

## Causa Raiz Confirmada

`/.auth/me` retorna **HTTP 401 Unauthorized + body vazio** (`Content-Length: 0`) para requisições sem sessão válida (cookie expirado, cookie cifrado com chave antiga, ou requisição feita antes do cookie ser estabelecido).

- `fetch()` resolve normalmente para respostas 4xx (não lança exceção)
- `r.json()` chamado sobre um body vazio lança `SyntaxError: Unexpected end of JSON input`
- O `.catch()` captura o `SyntaxError` e executa o fallback "Dev Local"
- O bloco `.then()` com o redirect para login **nunca é alcançado**

### Por que o body está vazio?

Easy Auth v2 com `unauthenticatedClientAction: "RedirectToLoginPage"` distingue requisições por tipo:
- Navegação do browser (`Accept: text/html`) → HTTP 302 redirect para login
- Requisição API (`fetch`, `curl`, XHR sem cabeçalho HTML) → HTTP 401 + body vazio + `WWW-Authenticate: Bearer ...`

Confirmado via `curl -si "https://app-financeirax01.azurewebsites.net/.auth/me"`:
```
HTTP/1.1 401 Unauthorized
Content-Length: 0
WWW-Authenticate: Bearer realm="..." authorization_uri="..."
```

### Cenários que causam sessão inválida

1. **Cookie expirado**: `timeToExpiration: "08:00:00"` — após 8h o cookie expira; usuário que deixou uma aba aberta recebe 401
2. **Cookie com chave antiga**: Kai definiu `WEBSITE_AUTH_ENCRYPTION_KEY` estável em 2026-05-28; cookies gerados antes desse fix foram cifrados com chave temporária e tornaram-se inválidos
3. **HTML cacheado**: Sem `Cache-Control: no-cache` no `index.html`, o browser pode carregar o React SPA do cache enquanto a sessão já expirou no servidor
4. **F1 tier / alwaysOn: false**: Container desliga com inatividade; ao reiniciar, cookies anteriores ficam inválidos se a chave não era estável (resolvido pelo fix da Kai)

## Fix Aplicado

### 1. `src/App/src/App.tsx` — guard `r.ok` antes de `r.json()`

Refatorado de `.then(r => r.json()).then(...).catch(...)` para `async/await` com guard explícito:

```ts
const r = await fetch("/.auth/me");
if (!r.ok) {
  window.location.href = `/.auth/login/aad?post_login_redirect_uri=...`;
  return; // nunca chama r.json() em body vazio
}
const data = await r.json(); // só alcançado em 2xx
```

**Resultado:** Sessão expirada → redirect para login (não mais "Dev Local").  
**Resultado:** Falha real de rede → `.catch()` → "Dev Local" (comportamento correto para dev local).

### 2. `src/App/nginx.conf` — criado (novo arquivo)

```nginx
location = /index.html {
    add_header Cache-Control "no-store, no-cache, must-revalidate, ...";
}
location /static/ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
location / {
    try_files $uri $uri/ /index.html;  # React Router SPA
}
```

**Resultado:** `index.html` nunca é cacheado → sessão expirada → App Service intercepta a navegação do browser e redireciona para login antes do React carregar.

### 3. `src/App/WebApp.Dockerfile` e `WebAppPatch.Dockerfile`

- Adicionado `COPY nginx.conf /etc/nginx/conf.d/default.conf`
- Corrigido `EXPOSE 3000` → `EXPOSE 80` (nginx escuta em 80; `WEBSITES_PORT` não está definido → App Service usa porta 80 por padrão)

## Passos para Deploy

```bash
# 1. Build imagem (se build/ já existe, usar WebAppPatch)
docker build -f src/App/WebAppPatch.Dockerfile \
  -t ckmcc0522172320.azurecr.io/webapp-financeirax:fix-auth-catch \
  src/App/

# 2. Push para ACR
docker push ckmcc0522172320.azurecr.io/webapp-financeirax:fix-auth-catch

# 3. Atualizar App Service
az webapp config container set \
  --name app-financeirax01 \
  --resource-group rg-callcenter-100 \
  --docker-custom-image-name ckmcc0522172320.azurecr.io/webapp-financeirax:fix-auth-catch

# 4. Reiniciar
az webapp restart --name app-financeirax01 --resource-group rg-callcenter-100
```

## Comunicação aos Usuários

> Após o deploy, todos os usuários precisam **limpar os cookies do browser** para `app-financeirax01.azurewebsites.net` e fazer login novamente. Cookies gerados antes de 2026-05-28 foram cifrados com chave temporária e estão inválidos.

## Questão em Aberto

Com `tokenStore.enabled: false` e sessão válida, `/.auth/me` retorna `[{user_id, user_claims, ...}]` (confirmado pela estrutura do código existente que funcionava antes). **Não há risco de loop de redirect** desde que o usuário tenha um cookie válido. Se investigação futura mostrar que `/.auth/me` retorna `[]` para sessões válidas, será necessário habilitar o token store com Blob Storage.

---

**Arquivos alterados:**
- `src/App/src/App.tsx` (linhas 479–512)
- `src/App/nginx.conf` (novo)
- `src/App/WebApp.Dockerfile`
- `src/App/WebAppPatch.Dockerfile`
