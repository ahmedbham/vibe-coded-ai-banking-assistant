# Architecture: AI Banking Assistant

## Objective

A banking personal assistant AI chat application that allows users to interact with their bank account information, transaction history, and payment functionalities. Leveraging generative AI within a multi-agent architecture, this assistant provides a seamless, conversational interface through which users can effortlessly access and manage their financial data.

---

## High-Level Architecture Diagram

```
┌───────────────────────────────────────────────────────────────────────┐
│                          Frontend Tier                                │
│                                                                       │
│   ┌───────────────────────────────────────────────────────────────┐   │
│   │          React Chat UI  (banking-web / simple-chat)           │   │
│   │   • TypeScript + Vite + shadcn/ui + Tailwind CSS              │   │
│   │   • Users ask banking questions in natural language           │   │
│   └───────────────────────┬───────────────────────────────────────┘   │
└───────────────────────────┼───────────────────────────────────────────┘
                            │ HTTPS / WebSocket
┌───────────────────────────▼───────────────────────────────────────────┐
│                          Middle Tier                                  │
│                                                                       │
│   ┌───────────────────────────────────────────────────────────────┐   │
│   │              AI Chat API  (FastAPI + Uvicorn)                  │   │
│   │   • Accepts natural-language prompts from the frontend        │   │
│   │   • Authenticated via Azure Managed Identity                  │   │
│   │   • Instrumented with Azure Monitor / OpenTelemetry           │   │
│   │                                                               │   │
│   │   ┌───────────────────────────────────────────────────────┐   │   │
│   │   │   Microsoft Agent Framework (MAF) Orchestration       │   │   │
│   │   │   deployed on Foundry Agent Service                   │   │   │
│   │   │                                                       │   │   │
│   │   │   ┌─────────────────┐  hand-off  ┌────────────────┐  │   │   │
│   │   │   │ Supervisor Agent├───────────►│ Account Agent  │  │   │   │
│   │   │   │  (triage /      │            └────────────────┘  │   │   │
│   │   │   │   routing)      │  hand-off  ┌────────────────┐  │   │   │
│   │   │   │                 ├───────────►│Transaction Agent│  │   │   │
│   │   │   │  GPT-4.1 via    │            └────────────────┘  │   │   │
│   │   │   │  Azure OpenAI   │  hand-off  ┌────────────────┐  │   │   │
│   │   │   │                 ├───────────►│ Payments Agent │  │   │   │
│   │   │   └─────────────────┘            └────────────────┘  │   │   │
│   │   └───────────────────────────────────────────────────────┘   │   │
│   └───────────────────────┬───────────────────────────────────────┘   │
└───────────────────────────┼───────────────────────────────────────────┘
                            │ MCP (FastMCP over HTTP)
┌───────────────────────────▼───────────────────────────────────────────┐
│                          Backend Tier                                 │
│                                                                       │
│   ┌─────────────────┐  ┌──────────────────────┐  ┌────────────────┐  │
│   │  Account Service│  │ Transactions Service  │  │Payments Service│  │
│   │  (Mock REST API)│  │   (Mock REST API)     │  │(Mock REST API) │  │
│   │                 │  │                       │  │                │  │
│   │  • Account info │  │ • Search transactions │  │ • Submit       │  │
│   │  • Credit balance│  │ • Get by recipient    │  │   payments     │  │
│   │  • Payment       │  │                       │  │                │  │
│   │    methods       │  │                       │  │                │  │
│   └────────┬────────┘  └──────────┬────────────┘  └───────┬────────┘  │
│            │                      │                        │           │
│   ┌────────▼──────────────────────▼────────────────────────▼────────┐  │
│   │                  FastMCP MCP Endpoint Layer                     │  │
│   │     Exposes each banking service as MCP tools for AI agents     │  │
│   └────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────┘
```

---

## Tier Breakdown

### 1. Frontend Tier

| Component | Technology |
|---|---|
| Chat UI | React 18.2+, TypeScript, Vite |
| Component Library | shadcn/ui (Radix UI primitives) |
| Styling | Tailwind CSS |
| Apps | `frontend/banking-web` (full banking UI), `frontend/simple-chat` (lightweight chat) |

**Responsibilities:**
- Present a conversational chat interface to the user.
- Send natural-language messages to the AI Chat API.
- Render structured responses (account balances, transaction lists, payment confirmations).

---

### 2. Middle Tier

#### AI Chat API

| Component | Technology |
|---|---|
| Web framework | FastAPI (async) + Uvicorn |
| AI models | Azure OpenAI GPT-4.1 (via MAF SDK) |
| Agent framework | Microsoft Agent Framework (MAF) |
| Agent hosting | Microsoft Foundry Agent Service |
| Authentication | Azure Identity (`DefaultAzureCredential`) |
| Observability | Azure Monitor + OpenTelemetry |

**Responsibilities:**
- Expose a chat endpoint consumed by the frontend.
- Authenticate requests and enforce authorization.
- Delegate work to the agent layer.

#### Agent Layer (MAF on Foundry Agent Service)

Four agents are composed using the **hand-off pattern**:

| Agent | Role | MCP Tool Used |
|---|---|---|
| **Supervisor Agent** | Triages every user request and routes it to the correct specialist agent | — |
| **Account Agent** | Handles account information, credit balance, and registered payment methods | Account Service MCP tool |
| **Transaction Agent** | Searches and retrieves transaction history | Transactions Service MCP tool |
| **Payments Agent** | Submits payments on behalf of the user | Payments Service MCP tool |

**Hand-off Pattern:**  
The Supervisor Agent receives every user prompt, determines intent, and transfers control to the appropriate specialist agent. Specialist agents use their bound MCP tools to call the backend APIs and return structured results to the Supervisor, which then synthesizes the final response for the user.

---

### 3. Backend Tier

#### Banking Services (Mock REST APIs)

| Service | Endpoints / Operations |
|---|---|
| **Account Service** | Get account information, check credit balance, list registered payment methods |
| **Transactions Service** | Search transactions, get transactions by recipient |
| **Payments Service** | Submit a payment |

All services are implemented as **mock REST APIs** (FastAPI) to simulate a real core banking system.

#### MCP Endpoint Layer (FastMCP)

Each banking service is wrapped with **FastMCP** to expose its operations as MCP-compliant tools. AI agents in the middle tier discover and call these tools through the MCP protocol, keeping the agent logic decoupled from the underlying REST implementation.

---

## Data Flow – Example: "Show me my last 5 transactions"

```
User (Chat UI)
    │  POST /chat  {"message": "Show me my last 5 transactions"}
    ▼
AI Chat API (FastAPI)
    │  Forward prompt to MAF agent runtime
    ▼
Supervisor Agent
    │  Intent: transaction history → hand-off to Transaction Agent
    ▼
Transaction Agent
    │  Call MCP tool: search_transactions(limit=5)
    ▼
FastMCP → Transactions Service (REST API)
    │  GET /transactions?limit=5
    ▼
Mock Transactions Service
    │  Returns JSON list of transactions
    ▼
Transaction Agent → Supervisor Agent
    │  Formats response
    ▼
AI Chat API
    │  Returns natural-language answer + structured data
    ▼
Chat UI  →  Displays result to user
```

---

## Infrastructure & Deployment

| Concern | Technology |
|---|---|
| Container hosting | Azure Container Apps |
| AI model serving | Microsoft Foundry (Azure AI Foundry) |
| Agent runtime | Foundry Agent Service |
| Infrastructure as Code | Bicep templates (`infra/`) |
| Container images | Multi-stage Docker builds (non-root user) |
| CI/CD | GitHub Actions (`.github/workflows/`) |
| Secrets management | Azure Key Vault (referenced via environment variables) |
| Observability | Azure Monitor + Application Insights |

---

## Repository Structure

```
.
├── .github/
│   └── workflows/          # GitHub Actions CI/CD pipelines
├── infra/                  # Bicep IaC templates
├── backend/
│   ├── agents/             # MAF agent implementations
│   │   ├── supervisor/     # Supervisor Agent
│   │   ├── account/        # Account Agent
│   │   ├── transactions/   # Transaction Agent
│   │   └── payments/       # Payments Agent
│   ├── mcp/                # FastMCP tool definitions
│   │   ├── account_mcp.py
│   │   ├── transactions_mcp.py
│   │   └── payments_mcp.py
│   ├── api/                # FastAPI routers (chat endpoint)
│   ├── services/           # Mock REST banking services
│   │   ├── account_service.py
│   │   ├── transactions_service.py
│   │   └── payments_service.py
│   ├── pyproject.toml      # Python dependencies (managed with uv)
│   └── Dockerfile
├── frontend/
│   ├── banking-web/        # Full banking React UI
│   └── simple-chat/        # Lightweight chat React UI
└── docs/
    └── architecture.md     # This document
```

---

## Security Considerations

- **No hard-coded secrets**: All credentials are stored in Azure Key Vault and referenced at runtime via environment variables.
- **Managed Identity**: All service-to-service communication uses Azure Managed Identities (`DefaultAzureCredential`).
- **No PII in logs**: Agents and API endpoints must never log personal or financial data.
- **Non-root containers**: All Docker images run as a non-root user.
- **Strict TypeScript**: Frontend code uses `"strict": true`; `any` types are prohibited without justification.
