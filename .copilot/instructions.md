# Project Instructions

## Project
- Name: Conversation-Knowledge-Mining-Solution-Accelerator
- Owner: Leme
- Team: alex (full-stack), kai (DevOps), morgan (tester)

## Stack and platform
- Frontend: React + TypeScript in `src/App/`
- Backend: FastAPI + Python in `src/api/`
- Hosting: Azure App Services
- Authentication: Easy Auth with Microsoft Entra ID (AAD)
- Data: SQL Server + Cosmos DB
- AI: Azure AI Foundry with GPT-4o-mini
- Containers: Azure Container Registry (ACR)

## Agent landscape
- ConversationAgent
- SearchAgent
- SQLAgent
- ChartAgent

## Working agreements
- Read `.squad/decisions.md` before making meaningful architectural changes.
- Prefer updating or adding docs in `docs/features/`, `docs/adr/`, and `docs/plans/` when the change affects scope, architecture, or delivery sequencing.
- Keep frontend changes focused under `src/App/` and backend changes focused under `src/api/`.
- Escalate Azure infrastructure concerns to kai and test ownership concerns to morgan.
- Preserve Easy Auth and Azure-native integration patterns unless a new ADR explicitly changes them.
