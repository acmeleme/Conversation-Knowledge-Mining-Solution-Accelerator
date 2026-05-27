# Scripts de Utilitários

## seed_memory_store.py

Script para popular o Azure AI Foundry Memory Store com conversas simuladas de call center.

### Propósito

Gera 100 conversas realistas em português brasileiro e alimenta o Memory Store configurado no projeto. Útil para:
- Testar funcionalidades de memória conversacional
- Demonstrar recuperação de contexto em conversas
- Popular ambiente de desenvolvimento com dados realistas

### Pré-requisitos

1. **SDK instalado**:
   ```bash
   pip install azure-ai-projects
   ```

2. **Variáveis de ambiente** (já configuradas no projeto):
   ```bash
   AZURE_AI_PROJECT_ENDPOINT=<seu-endpoint>
   AZURE_AI_MEMORY_STORE_NAME=memory-store-callcenter-100
   AZURE_AI_MEMORY_ENABLED=true
   ```

3. **Autenticação Azure** via `az login`:
   ```bash
   az login
   ```

### Uso

Execute a partir do diretório raiz do projeto:

```bash
python scripts/seed_memory_store.py
```

### O que o script faz

1. **Gera 100 conversas** em 6 categorias:
   - 🛒 Vendas e consultas de produtos
   - 🔧 Suporte técnico
   - 😠 Reclamações
   - 📦 Status de pedidos
   - 👤 Gerenciamento de conta
   - ℹ️ Informações gerais

2. **Características das conversas**:
   - 2 turnos cada (pergunta do usuário + resposta do assistente)
   - Variações automáticas de saudações
   - Conteúdo realista em português brasileiro

3. **Gravação no Memory Store**:
   - Usa o scope correto: `tenant_2e50c5c4-4293-4a30-8a9c-0d9fb964a55a__user_1e7cc145-ed07-4f8a-8779-502ad993ccf5`
   - Retry automático em caso de rate limits (3 tentativas)
   - Delay de 0.5s entre conversas para evitar throttling
   - Delay de 5s para processamento de memórias (conforme configuração)

4. **Progresso**:
   - Atualização a cada 10 conversas
   - Relatório final com sucesso/falhas
   - Tempo total e média por conversa

### Saída esperada

```
============================================================
🚀 Iniciando população do Memory Store
============================================================
Memory Store: memory-store-callcenter-100
Scope: tenant_2e50c5c4-4293-4a30-8a9c-0d9fb964a55a__user_1e7cc145-ed07-4f8a-8779-502ad993ccf5
Endpoint: https://...

✅ Cliente Azure AI Projects criado com sucesso
📝 100 conversas geradas

📊 Progresso: 10/100 conversas processadas
📊 Progresso: 20/100 conversas processadas
...
📊 Progresso: 100/100 conversas processadas

============================================================
✨ População do Memory Store concluída!
============================================================
✅ Conversas criadas com sucesso: 100/100
⏱️  Tempo total: 65.3 segundos
📈 Média: 0.65 segundos por conversa

🔍 Verifique as memórias no portal do Azure AI Foundry:
   Memory Store: memory-store-callcenter-100
   Scope: tenant_2e50c5c4-4293-4a30-8a9c-0d9fb964a55a__user_1e7cc145-ed07-4f8a-8779-502ad993ccf5
============================================================
```

### Verificação

Após executar o script, verifique as memórias no portal do Azure AI Foundry:
1. Acesse o Azure AI Foundry Studio
2. Navegue até **Memory Stores**
3. Selecione `memory-store-callcenter-100`
4. Filtre pelo scope especificado acima
5. Você deverá ver 100 conversas com diferentes temas

### Customização

Para ajustar o comportamento do script, edite as constantes no arquivo:

- `MAX_RETRIES`: Número de tentativas em caso de rate limit (padrão: 3)
- `RETRY_DELAY_BASE`: Base para cálculo do delay exponencial (padrão: 2 segundos)
- `UPDATE_DELAY_SECONDS`: Delay para processamento de memórias (padrão: 5 segundos)

Para adicionar novos tipos de conversas, adicione tuplas nas listas:
- `CONVERSAS_VENDAS`
- `CONVERSAS_SUPORTE`
- `CONVERSAS_RECLAMACOES`
- `CONVERSAS_STATUS`
- `CONVERSAS_CONTA`
- `CONVERSAS_EXTRAS`

### Troubleshooting

**Erro: AZURE_AI_PROJECT_ENDPOINT não está configurado**
- Verifique se a variável de ambiente está setada
- Ou edite o script e defina diretamente: `PROJECT_ENDPOINT = "https://..."`

**Erro: azure-ai-projects não está instalado**
- Execute: `pip install azure-ai-projects`

**Rate limit (429)**
- O script já trata automaticamente com retry exponencial
- Se persistir, aumente `RETRY_DELAY_BASE` ou diminua a frequência

**Autenticação falhou**
- Execute `az login` e selecione a conta correta
- Verifique permissões no Azure AI Project
