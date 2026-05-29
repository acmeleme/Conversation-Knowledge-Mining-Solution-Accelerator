# E2E Test Guide — Conversation Knowledge Mining

> **QA Owner:** Morgan  
> **Last updated:** 2026-05-29  
> **Stack:** Playwright (sync) + Pytest

---

## Pré-requisitos

| Requisito | Comando / Detalhe |
|-----------|-------------------|
| Python 3.11+ | `python --version` |
| Dependências instaladas | `pip install -r requirements.txt` |
| Variáveis de ambiente | Copiar `sample_dotenv_file.txt` → `.env` e preencher |
| App em execução | Frontend + Backend acessíveis na URL configurada em `.env` |
| Conta Microsoft Entra ID | Usuário com role `callcenter` ou `faturamento` (ver abaixo) |

### Variáveis de ambiente obrigatórias (`.env`)

```
URL=https://<seu-app>.azurewebsites.net
# Apenas se for usar autenticação programática:
USERNAME=usuario@contoso.com
PASSWORD=*****
```

---

## Como executar

### Todos os testes E2E de autenticação

```bash
cd tests/e2e-test
python -m pytest tests/test_entra_auth_e2e.py -v
```

### Com relatório HTML

```bash
python -m pytest tests/test_entra_auth_e2e.py -v --html=report.html --self-contained-html
```

### Um teste específico pelo ID

```bash
python -m pytest "tests/test_entra_auth_e2e.py::test_entra_auth_success_criteria[04. C4: No 'Visitante' card...]" -v
```

---

## O que cada teste verifica

| ID | Critério | Comportamento esperado |
|----|----------|------------------------|
| **C1** | Entra ID auth ativo | A tela de seleção de perfil **demo** (`Modo Demonstração`) não aparece. O app carrega direto com o usuário autenticado. |
| **C2** | Sem texto "Demo" | A string literal `"Demo"` não aparece em nenhum lugar do DOM visível. |
| **C3** | Avatar → popover de perfil | Clicar no avatar abre um popover com botões "Ver Perfil" e "Trocar Perfil". O popover contém dados do usuário Entra ID. |
| **C3b** | Nome real no popover | O nome exibido no popover não é vazio, nem `"Usuário Demo"`, nem `"Dev Local"`. |
| **C4** | Sem card "Visitante" | Se a tela de seleção de perfil aparecer, ela contém **apenas** os cards "Financeiro & Faturamento" e "Operador de Callcenter". O card "Visitante" foi removido e não deve existir. Se o usuário já está autenticado e a tela não aparece, o teste passa vacuosamente. |
| **C5** *(negativo)* | Tela "Acesso Negado" | Se um usuário sem role válida acessa o app, a tela exibe `"🚫 Acesso Negado"` e o botão `"Sair"`. Em sessões válidas, o teste passa vacuosamente (tela não aparece). |

---

## Fluxo de autenticação esperado

```
Usuário → App URL
    → Redirecionamento MSAL (Microsoft Entra ID)
    → Login com conta @contoso.com
    → App recebe token com claims de role
    ↓
  role == "faturamento"  →  Tela "Financeiro & Faturamento" + app carrega
  role == "callcenter"   →  Tela "Operador de Callcenter"  + app carrega
  role == nenhuma        →  Tela "🚫 Acesso Negado" + botão "Sair"
  (role "callcenter" como Visitante foi REMOVIDA)
```

---

## Roles válidas após a mudança do Alex (2026-05-29)

| Role (claim Entra ID) | Label na UI | Card no login |
|-----------------------|-------------|---------------|
| `faturamento` | 💼 Financeiro & Faturamento | ✅ Existe |
| `callcenter` (operador) | 🎧 Operador de Callcenter | ✅ Existe |
| ~~`callcenter` (visitante)~~ | ~~Visitante~~ | ❌ **REMOVIDO** |
| *(sem role)* | — | 🚫 Acesso Negado |

---

## Estrutura dos arquivos de teste

```
tests/e2e-test/
├── pages/
│   ├── authPage.py        # Page Object: avatar, popover, visitor card, access denied
│   └── loginPage.py       # Page Object: login Entra ID (email/senha)
├── tests/
│   ├── conftest.py        # Fixtures de sessão (login_logout, hooks HTML)
│   └── test_entra_auth_e2e.py  # Testes C1–C5
├── base/base.py           # BasePage (scroll, request helpers)
├── config/constants.py    # URL, API_URL, etc.
├── pytest.ini             # Configuração pytest
└── E2E_TEST_GUIDE.md      # Este arquivo
```

---

## Troubleshooting

| Sintoma | Causa provável | Solução |
|---------|----------------|---------|
| `AssertionError: Main application did not load` | App offline ou timeout curto | Aumentar `timeout` em `wait_for_app_loaded` ou verificar se o app está rodando |
| C1 falha — role selector visível | App em modo demo (sem Entra ID configurado) | Configurar `AZURE_CLIENT_ID`, `AZURE_TENANT_ID` no backend |
| C2 falha — "Demo" visível | Texto de demo não removido do frontend | Verificar componentes React que referenciam `"Demo"` |
| C4 falha — card Visitante presente | Frontend não atualizado com a mudança do Alex | Re-fazer o build do frontend (`npm run build`) |
| C5 dispara em sessão válida | Usuário não tem role no Entra ID | Verificar atribuição de app roles no portal Azure |
