"""
deploy_workflow.py
──────────────────
Registers the CallCenterInsightWorkflow in Azure AI Foundry using the
Python SDK (azure-ai-projects).

Usage:
    pip install azure-ai-projects azure-identity pyyaml
    az login
    python deploy_workflow.py

Required environment variables (see .env.example):
    AZURE_FOUNDRY_PROJECT_ENDPOINT
    AZURE_FOUNDRY_GPT_MODEL        (default: gpt-4o)
"""

import io
import os
import sys
import yaml
from pathlib import Path

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, WorkflowAgentDefinition
from azure.identity import AzureCliCredential

PROJECT_ENDPOINT = os.environ["AZURE_FOUNDRY_PROJECT_ENDPOINT"]
MODEL = os.environ.get("AZURE_FOUNDRY_GPT_MODEL", "gpt-4o-mini")
WORKFLOW_YAML_PATH = Path(__file__).parent / "workflow.yaml"
PROMPT_PATH = Path(__file__).parent / "call_center_analyst_prompt.jinja2"

SEARCH_AGENT_INSTRUCTIONS = (
    "You are a search assistant. Retrieve the most relevant call center records "
    "from the knowledge base for the user's query. Return all results verbatim "
    "with chunk_id, source_file, call_date, agent_id, and content. Do not summarise."
)

SEPARATOR = "=" * 60


def main():
    print(SEPARATOR)
    print("  Deploying CallCenterInsightWorkflow to Azure AI Foundry")
    print(SEPARATOR)
    print(f"  Project: {PROJECT_ENDPOINT}")
    print(f"  Model:   {MODEL}")
    print()

    client = AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=AzureCliCredential(),
        allow_preview=True,
    )

    # ── Agent 1: KMSearchAgent ───────────────────────────────────────────────
    # NOTE: The Azure AI Search tool connection must be pre-configured in Foundry.
    # This script registers the agent definition; attach the Search tool in the UI
    # or via the tool configuration API after creation.
    print("Creating KMSearchAgent...")
    search_agent = client.agents.create_version(
        agent_name="KMSearchAgent",
        definition=PromptAgentDefinition(
            model=MODEL,
            instructions=SEARCH_AGENT_INSTRUCTIONS,
        ),
        description="Queries km_processed_data index with hybrid semantic+vector search",
    )
    print(f"  ✅ KMSearchAgent: {search_agent.name}")

    # ── Agent 2: CallCenterAnalystAgent ──────────────────────────────────────
    print("Creating CallCenterAnalystAgent...")
    analyst_instructions = PROMPT_PATH.read_text(encoding="utf-8")
    analyst_agent = client.agents.create_version(
        agent_name="CallCenterAnalystAgent",
        definition=PromptAgentDefinition(
            model=MODEL,
            instructions=analyst_instructions,
        ),
        description="GPT-4o call center analyst — generates structured intelligence reports",
    )
    print(f"  ✅ CallCenterAnalystAgent: {analyst_agent.name}")

    # ── Workflow registration ─────────────────────────────────────────────────
    print("Registering workflow...")
    workflow_yaml = WORKFLOW_YAML_PATH.read_text(encoding="utf-8")

    workflow_agent = client.agents.create_version(
        agent_name="CallCenterInsightWorkflow",
        definition=WorkflowAgentDefinition(workflow=workflow_yaml),
        description="Sequential workflow: search km_processed_data → GPT-4o analyst report",
    )
    print(f"  ✅ Workflow: {workflow_agent.name}")

    print()
    print(SEPARATOR)
    print("  Deployment Complete!")
    print(SEPARATOR)
    print(f"  Workflow ID: {workflow_agent.name}")
    print()
    print("  Next steps:")
    print("  1. Open ai.azure.com → your project → Workflows")
    print("  2. Find 'CallCenterInsightWorkflow' and click Run Workflow")
    print("  3. Test with: 'What are the most common billing complaints?'")
    print()
    print("  ⚠️  Remember to attach the Azure AI Search tool to KMSearchAgent")
    print("     in the Foundry portal → Agents → KMSearchAgent → Tools → Add tool")


if __name__ == "__main__":
    main()
