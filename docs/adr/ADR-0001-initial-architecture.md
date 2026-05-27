# ADR-0001: Initial architecture baseline

- Status: Accepted
- Date: 2026-05-25
- Owner: Leme

## Context
The repository needs an initial SDD baseline that reflects the current application shape and provides a stable reference for future feature specs and delivery plans.

The solution accelerator is owned by Leme and delivered by a small team:
- alex — full-stack development
- kai — DevOps and Azure infrastructure
- morgan — testing and validation

The current product direction is a web application for conversation knowledge mining with a React frontend, a FastAPI backend, Azure-hosted services, and multiple specialized AI agents.

## Decision
Adopt the following architecture baseline:

### Application stack
- Frontend: React + TypeScript
- Backend: FastAPI (Python)
- Hosting: Azure App Services
- Authentication: Easy Auth with Microsoft Entra ID (AAD)
- Storage: SQL Server for structured application data and Cosmos DB for flexible/document-oriented data
- AI platform: Azure AI Foundry using GPT-4o-mini
- Container registry: Azure Container Registry (ACR)

### Agent baseline
The backend solution recognizes the following agent roles as part of the product design:
- ConversationAgent
- SearchAgent
- SQLAgent
- ChartAgent

## Consequences
- Frontend work should align with React and TypeScript conventions under the web application.
- Backend APIs, orchestration, and service logic should align with FastAPI and Python conventions.
- Authentication and authorization flows should integrate with Easy Auth and AAD instead of implementing a separate identity provider.
- Data design can split structured records and transactional needs into SQL Server while keeping flexible or high-scale document data in Cosmos DB.
- AI capabilities should be planned against Azure AI Foundry and GPT-4o-mini constraints, including prompt, latency, and cost considerations.
- Container image workflows should assume ACR as the image distribution boundary for Azure deployments.

## Notes
This ADR captures the initial architecture already chosen for the project. Future ADRs can refine deployment topology, agent orchestration details, data ownership boundaries, or observability standards without replacing this baseline unless explicitly superseded.
