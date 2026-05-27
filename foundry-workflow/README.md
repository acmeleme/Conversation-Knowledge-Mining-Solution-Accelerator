# foundry-workflow/

This folder contains everything needed to run the **Call Center Knowledge Mining** workflow in **Azure AI Foundry (New Foundry)** — the new agent orchestration system at `ai.azure.com` with the "New Foundry" toggle ON.

> ⚠️ **Not Prompt Flow.** The old `flow.dag.yaml` (Prompt Flow / Foundry classic) is deprecated as of April 2026. This folder now uses the new **Agent Framework Workflow** format.

---

## Files

| File | Purpose |
|---|---|
| `workflow.yaml` | ✅ **Main file** — new Agent Framework YAML for the 2-node sequential workflow |
| `call_center_analyst_prompt.jinja2` | System prompt for the `CallCenterAnalystAgent` (paste into agent Instructions) |
| `search_km_data.py` | Legacy Prompt Flow Python tool — kept as reference; the search logic now runs inside `KMSearchAgent`'s built-in Azure AI Search tool |
| `deploy_workflow.py` | Python SDK script to register agents + workflow programmatically |
| `.env.example` | Environment variable template |
| `flow.dag.yaml` | ⚠️ **Deprecated** — old Prompt Flow schema, kept for reference only |

---

## How the Workflow Works

```
User Question
     │
     ▼
┌─────────────────────────────┐
│  KMSearchAgent              │  → Azure AI Search tool
│  (Azure AI Search, top-5,   │    index: km_processed_data
│   hybrid semantic+vector)   │    mode:  hybrid + semantic reranking
└─────────────┬───────────────┘
              │  Local.SearchResults
              ▼
┌─────────────────────────────┐
│  CallCenterAnalystAgent     │  → GPT-4o
│  (system prompt from        │    generates structured report
│   call_center_analyst_      │    with citations + recommendations
│   prompt.jinja2)            │
└─────────────┬───────────────┘
              │
              ▼
      Intelligence Report → user
```

---

## Option A — Build Visually in the Foundry Portal (Recommended)

> **New Foundry toggle must be ON** at `ai.azure.com`

### Step 1 — Create the two Foundry Agents

Go to **Foundry portal → Agents → + New agent**:

#### Agent 1: `KMSearchAgent`
- **Model**: `gpt-4o` (or `gpt-4o-mini`)
- **Instructions**:
  ```
  You are a search assistant. Retrieve the most relevant call center records
  from the knowledge base for the user's query. Return all results verbatim
  with chunk_id, source_file, call_date, agent_id, and content. Do not summarise.
  ```
- **Tools → Add tool → Azure AI Search**:
  - Index: `km_processed_data`
  - Query mode: Hybrid (semantic + vector)
  - Top-N: `5`
  - Semantic config: `km-semantic-config`
  - Fields: `chunk_id`, `content`, `source_file`, `call_date`, `agent_id`

#### Agent 2: `CallCenterAnalystAgent`
- **Model**: `gpt-4o`
- **Instructions**: Paste the **full content** of `call_center_analyst_prompt.jinja2`
- **Response format** (optional): Set to JSON Schema (see schema block in `workflow.yaml`)
- **Tools**: None required

### Step 2 — Create the Workflow

1. In the Foundry portal, go to **Workflows → + New workflow**
2. Select **Sequential** template
3. Click the **+** between Start and End nodes:
   - Add **"Invoke agent"** → select `KMSearchAgent`
   - Set output to `Local.SearchResults`, toggle `autoSend` OFF
4. Add another **"Invoke agent"** → select `CallCenterAnalystAgent`
   - Set input to `Local.SearchResults`
   - Toggle `autoSend` ON
5. Click **Save**
6. Click **Run Workflow** to test in the chat panel

---

## Option B — Paste via YAML Tab

1. Open your workflow in the Foundry portal
2. In the top-right of the workflow builder, toggle **"YAML Visualizer View" → ON**
3. Select the **YAML** tab
4. Replace the content with `workflow.yaml` from this folder
5. Click **Save** — the visual canvas updates automatically

> **Note**: The YAML tab is a two-way editor. Changes in YAML appear in the canvas and vice versa. This is NOT a separate import button — you edit YAML in-place.

---

## Option C — Deploy via Python SDK

Use `deploy_workflow.py` to register both agents and the workflow programmatically:

```bash
# Install dependencies
pip install azure-ai-projects azure-identity pyyaml

# Authenticate
az login

# Deploy
python deploy_workflow.py
```

Required environment variables (copy `.env.example` → `.env`):

```env
AZURE_FOUNDRY_PROJECT_ENDPOINT=https://<account>.services.ai.azure.com/api/projects/<project>
AZURE_FOUNDRY_GPT_MODEL=gpt-4o
AZURE_SEARCH_ENDPOINT=https://<search>.search.windows.net
AZURE_SEARCH_INDEX=km_processed_data
```

---

## Testing the Workflow

In the Foundry portal chat panel (after clicking **Run Workflow**), send:

```
What are the most common complaints about billing errors?
```

Expected response: a structured intelligence report with:
- 🔴 Top 3 Issues with `chunk_id` citations
- 😟 Customer Sentiment Analysis
- ✅ Recommended Actions
- 💬 Representative Quote
- 📚 Sources Used

---

## Key Differences: Old Prompt Flow vs New Agent Workflows

| | Old (`flow.dag.yaml`) | New (`workflow.yaml`) |
|---|---|---|
| Schema | `$schema: azuremlschemas...Flow.schema.json` | `kind: workflow` (Agent Framework) |
| Node types | `type: python`, `type: llm` | `kind: InvokeAzureAgent`, `kind: SetVariable` |
| Search | Python code (`search_km_data.py`) | Built-in Azure AI Search tool on agent |
| LLM | Jinja2 template + connection | Agent Instructions field + model selection |
| Variables | `${inputs.foo}` / `${node.output}` | `=Local.Foo` (Power Fx expressions) |
| Import | Upload folder zip | YAML tab (in-place edit) or Python SDK |
| Status | ⚠️ Retired April 2026 | ✅ Current |
