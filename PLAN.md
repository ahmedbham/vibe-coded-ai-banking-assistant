# PLAN.md – Multi-Agent Banking Assistant: Build Plan

This document breaks the three-tier multi-agent banking assistant (see [`docs/architecture.md`](docs/architecture.md)) into a series of logical, independently testable GitHub Issues. Each issue produces a runnable, verifiable increment so it can be assigned, reviewed, and tested in isolation before the next step begins.

---

## Architecture Summary

```
┌─────────────────┐     HTTPS      ┌───────────────────────────────────┐     MCP/HTTP     ┌──────────────────────────────────┐
│  Frontend Tier  │ ─────────────► │          Middle Tier               │ ───────────────► │         Backend Tier             │
│                 │                │                                   │                  │                                  │
│  banking-web    │                │  FastAPI AI Chat API              │                  │  Account Service  (Mock REST)    │
│  simple-chat    │                │  ┌─────────────────────────────┐  │                  │  Transactions Service (Mock REST) │
│  React + TS     │                │  │  Supervisor Agent  (MAF)    │  │                  │  Payments Service (Mock REST)     │
│  Vite + shadcn  │                │  │  Account Agent     (MAF)    │  │                  │                                  │
│                 │                │  │  Transaction Agent (MAF)    │  │                  │  FastMCP layer                   │
│                 │                │  │  Payment Agent     (MAF)    │  │                  │  (MCP tools over HTTP streaming) │
└─────────────────┘                │  └─────────────────────────────┘  │                  └──────────────────────────────────┘
                                   └───────────────────────────────────┘
```

**Azure AI Foundry** provides GPT-4.1 (Azure OpenAI) and Azure Document Intelligence (invoice scanning).  
All services are hosted on **Azure Container Apps**; infrastructure is defined in **Bicep**.

---

## Issues / Steps

### Issue 1 – Repository Scaffolding & Project Structure

**Goal:** Establish the full directory layout and tooling baseline so every subsequent issue has a consistent home.

**Tasks:**
- Create the canonical directory tree:
  ```
  backend/agents/{supervisor,account,transactions,payments}/
  backend/mcp/
  backend/api/
  backend/services/
  frontend/banking-web/
  frontend/simple-chat/
  infra/
  .github/workflows/
  ```
- Add `backend/pyproject.toml` with `uv`-managed Python 3.11+ dependencies (FastAPI, Uvicorn, pytest, ruff, etc.).
- Add root-level `.gitignore`, `README.md` updates.
- Add a minimal `backend/Dockerfile` (multi-stage, non-root user) that just builds the Python environment.
- Add a GitHub Actions workflow (`ci.yml`) that runs `uv pip install` and `pytest` (empty suite passes).

**Testable outcome:** `docker build` succeeds; `pytest` runs with zero tests and exits 0; CI workflow passes.

---

### Issue 2 – Mock Account Service (Backend Tier)

**Goal:** Implement the Account Service as a standalone FastAPI mock REST API that can be run and tested independently.

**Endpoints to implement:**
| Method | Path | MCP Tool |
|--------|------|----------|
| `GET` | `/accounts/{username}` | `getAccountByUsername` |
| `GET` | `/accounts/{account_id}/details` | `getAccountDetails` |
| `GET` | `/accounts/{account_id}/payment-methods` | `getPaymentMethods` |
| `GET` | `/accounts/{account_id}/beneficiaries` | `getRegisteredBeneficiaries` |

**Tasks:**
- Implement `backend/services/account_service.py` with in-memory mock data.
- Add `pytest` unit tests in `backend/tests/test_account_service.py` covering each endpoint (happy path + 404).
- Expose the service on port `8001`; document with FastAPI's auto-generated OpenAPI UI.

**Testable outcome:** `pytest backend/tests/test_account_service.py` passes; `GET /accounts/john_doe` returns mock JSON.

---

### Issue 3 – Mock Transactions (Reporting) Service (Backend Tier)

**Goal:** Implement the Transactions/Reporting Service as a standalone FastAPI mock REST API.

**Endpoints to implement:**
| Method | Path | MCP Tool |
|--------|------|----------|
| `POST` | `/transactions/notify` | `notifyTransaction` |
| `GET` | `/transactions/search` | `searchTransactions` |
| `GET` | `/transactions/by-recipient/{recipient_id}` | `getTransactionByRecipient` |

**Tasks:**
- Implement `backend/services/transactions_service.py` with in-memory mock data.
- Add `pytest` unit tests in `backend/tests/test_transactions_service.py`.
- Expose on port `8003`.

**Testable outcome:** `pytest backend/tests/test_transactions_service.py` passes; `GET /transactions/search?query=coffee` returns mock results.

---

### Issue 4 – Mock Payments Service (Backend Tier)

**Goal:** Implement the Payments Service as a standalone FastAPI mock REST API.

**Endpoints to implement:**
| Method | Path | MCP Tool |
|--------|------|----------|
| `POST` | `/payments` | `submitPayment` |

**Tasks:**
- Implement `backend/services/payments_service.py` with in-memory mock data and basic validation.
- Add `pytest` unit tests in `backend/tests/test_payments_service.py` (success, missing fields, duplicate detection).
- Expose on port `8002`.

**Testable outcome:** `pytest backend/tests/test_payments_service.py` passes; `POST /payments` returns a payment confirmation ID.

---

### Issue 5 – FastMCP Layer (Backend Tier)

**Goal:** Wrap each mock service with **FastMCP** to expose its operations as MCP-compliant tools consumable by AI agents over HTTP Streaming.

**Tasks:**
- Implement `backend/mcp/account_mcp.py` exposing `getAccountByUsername`, `getAccountDetails`, `getPaymentMethods`, `getRegisteredBeneficiaries` as MCP tools.
- Implement `backend/mcp/transactions_mcp.py` exposing `notifyTransaction`, `searchTransactions`, `getTransactionByRecipient`.
- Implement `backend/mcp/payments_mcp.py` exposing `submitPayment`.
- Each MCP server calls the corresponding mock service over HTTP (configurable base URL via environment variables).
- Add `pytest` tests that call each MCP tool directly (using the FastMCP test client) and verify the response schema.
- Expose each MCP server on its own port (`9001`, `9002`, `9003`) so they can be tested independently.

**Testable outcome:** `pytest backend/tests/test_mcp_*.py` passes; MCP tool calls return valid responses without a live Azure environment.

---

### Issue 6 – Azure Document Intelligence Integration (ScanInvoice Tool)

**Goal:** Add the `ScanInvoice` MCP tool used by the Payment Agent to extract invoice data from uploaded images/PDFs using Azure Document Intelligence.

**Tasks:**
- Implement `backend/mcp/document_mcp.py` wrapping the Azure Document Intelligence `prebuilt-invoice` model.
- Use `DefaultAzureCredential` for authentication; accept the endpoint via environment variable `DOCUMENT_INTELLIGENCE_ENDPOINT`.
- Expose a `scanInvoice(file_url: str) -> InvoiceData` MCP tool returning extracted fields (vendor, amount, due date, etc.).
- Add unit tests using `pytest` + `unittest.mock` to mock the Azure SDK calls and verify field extraction logic.
- Document required Azure resource setup in a `docs/setup-document-intelligence.md` file.

**Testable outcome:** `pytest backend/tests/test_document_mcp.py` passes with mocked Azure SDK; real call succeeds against a provisioned Document Intelligence resource.

---

### Issue 7 – Account Agent (Middle Tier)

**Goal:** Implement the **Account Agent** using the Microsoft Agent Framework (MAF), bound to the Account Service MCP tools.

**Tasks:**
- Implement `backend/agents/account/agent.py` using MAF, configured with:
  - System prompt scoped to account information, credit balance, and payment methods.
  - MCP tool binding to `account_mcp` (URL configurable via environment variable).
  - GPT-4.1 via Azure OpenAI (`DefaultAzureCredential`).
- Add unit tests in `backend/tests/test_account_agent.py` mocking the MAF SDK and MCP tool calls.
- Add an integration test that runs the agent against the local mock MCP server (Issue 5).

**Testable outcome:** `pytest backend/tests/test_account_agent.py` passes; running the agent locally returns account info for a mock user.

---

### Issue 8 – Transaction Agent (Middle Tier)

**Goal:** Implement the **Transaction Agent** using MAF, bound to the Account and Transactions MCP tools.

**Tasks:**
- Implement `backend/agents/transactions/agent.py` using MAF, configured with:
  - System prompt scoped to transaction history queries.
  - MCP tool bindings to `account_mcp` (API1) and `transactions_mcp` (API3).
  - GPT-4.1 via Azure OpenAI.
- Add unit and integration tests in `backend/tests/test_transaction_agent.py`.

**Testable outcome:** `pytest backend/tests/test_transaction_agent.py` passes; agent returns a formatted list of mock transactions.

---

### Issue 9 – Payment Agent (Middle Tier)

**Goal:** Implement the **Payment Agent** using MAF, bound to Account, Payments, Transactions, and ScanInvoice MCP tools.

**Tasks:**
- Implement `backend/agents/payments/agent.py` using MAF, configured with:
  - System prompt scoped to submitting payments and processing invoices.
  - MCP tool bindings to `account_mcp` (API1), `payments_mcp` (API2), `transactions_mcp` (API3), and `document_mcp` (ScanInvoice).
  - GPT-4.1 via Azure OpenAI.
- Handle both `Intent=PayInvoice` (scan invoice → submit payment) and `Intent=RepeatPayment` (look up previous payment → resubmit) flows.
- Add unit and integration tests in `backend/tests/test_payment_agent.py`.

**Testable outcome:** `pytest backend/tests/test_payment_agent.py` passes; agent correctly submits a payment from a mock invoice scan.

---

### Issue 10 – Supervisor Agent (Middle Tier)

**Goal:** Implement the **Supervisor Agent** using MAF to triage user messages and hand off to the correct specialist agent.

**Tasks:**
- Implement `backend/agents/supervisor/agent.py` using MAF with the hand-off pattern:
  - Intent routing: `AccountInfo` → Account Agent, `Transactions` → Transaction Agent, `PayInvoice` / `RepeatPayment` → Payment Agent.
  - GPT-4.1 system prompt for intent classification and response synthesis.
- Register all three specialist agents as hand-off targets.
- Add unit tests validating routing logic and integration tests validating end-to-end hand-off with mock agents.

**Testable outcome:** `pytest backend/tests/test_supervisor_agent.py` passes; "Show me my balance" is routed to the Account Agent; "Pay my electricity bill" is routed to the Payment Agent.

---

### Issue 11 – AI Chat API (Middle Tier FastAPI)

**Goal:** Expose a single `/chat` HTTP endpoint that fronts the Supervisor Agent and returns streaming responses.

**Tasks:**
- Implement `backend/api/chat.py` as a FastAPI router:
  - `POST /chat` accepts `{ "message": str, "session_id": str }` and returns a streaming response.
  - Authenticated with Azure Managed Identity (`DefaultAzureCredential`).
  - Instrumented with Azure Monitor OpenTelemetry.
- Wire all agents and MCP servers together in `backend/main.py`.
- Add `pytest` tests for the `/chat` endpoint using `httpx.AsyncClient` with mocked agent responses.
- Add a `docker-compose.yml` at the repo root for local end-to-end development (all services + MCP servers + API).

**Testable outcome:** `pytest backend/tests/test_chat_api.py` passes; `curl -X POST /chat -d '{"message":"What is my balance?"}'` returns a streamed response.

---

### Issue 12 – Simple Chat Frontend (`frontend/simple-chat`)

**Goal:** Build the lightweight React chat UI that talks to the AI Chat API.

**Tasks:**
- Scaffold `frontend/simple-chat` with Vite + React 18.2 + TypeScript (strict) + Tailwind CSS + shadcn/ui.
- Implement a single-page chat interface with:
  - Message input box and send button.
  - Chat message list (user and assistant bubbles).
  - Streaming response rendering (incremental text).
  - Basic error and loading states.
- Configure the API base URL via `VITE_API_URL` environment variable.
- Add component tests using Vitest + React Testing Library for the chat components.
- Add a `Dockerfile` for the frontend.

**Testable outcome:** `npm run test` passes; `npm run dev` serves a chat UI that connects to the local AI Chat API; Docker image builds.

---

### Issue 13 – Full Banking Web Frontend (`frontend/banking-web`)

**Goal:** Build the full React banking UI with richer data display on top of the chat interface.

**Tasks:**
- Scaffold `frontend/banking-web` with Vite + React 18.2 + TypeScript (strict) + Tailwind CSS + shadcn/ui.
- Implement views:
  - Chat panel (reuse simple-chat components).
  - Account summary card (balance, payment methods).
  - Transaction history table (paginated).
  - Payment form with optional invoice upload (triggers ScanInvoice).
- Connect all views to the AI Chat API or directly to backend mock services via REST for display.
- Add component tests using Vitest + React Testing Library.
- Add a `Dockerfile`.

**Testable outcome:** `npm run test` passes; `npm run dev` serves a full banking dashboard with chat; Docker image builds.

---

### Issue 14 – Azure Infrastructure (Bicep)

**Goal:** Define all Azure resources needed to host the application in Azure Container Apps using Bicep IaC.

**Resources to define:**
- Azure Container Registry (ACR) for container images.
- Azure Container Apps Environment + individual Container Apps for:
  - `backend-api` (AI Chat API)
  - `account-service`, `transactions-service`, `payments-service` (Mock REST)
  - `account-mcp`, `transactions-mcp`, `payments-mcp`, `document-mcp` (FastMCP)
  - `frontend-banking-web`, `frontend-simple-chat`
- Azure AI Foundry project + Foundry Agent Service deployment.
- Azure OpenAI resource with GPT-4.1 deployment.
- Azure Document Intelligence resource.
- Azure Key Vault for secrets.
- Azure Monitor + Application Insights workspace.
- Managed Identity with role assignments.

**Tasks:**
- Implement modular Bicep templates under `infra/` (one module per resource type).
- Parameterise all environment-specific values (`environment`, `location`, `project`, `owner` tags on every resource).
- Add a `deploy.sh` script that provisions resources with `az deployment group create`.
- Validate templates with `az bicep build` in CI.

**Testable outcome:** `az bicep build --file infra/main.bicep` succeeds; `az deployment group create --what-if` completes without errors against a test subscription.

---

### Issue 15 – Docker & Local docker-compose Setup

**Goal:** Ensure every service can be built as a Docker image and the full stack can be run locally with `docker compose up`.

**Tasks:**
- Finalise multi-stage `Dockerfile` for `backend/` (non-root user, minimal image).
- Finalise `Dockerfile` for `frontend/banking-web` and `frontend/simple-chat`.
- Create `docker-compose.yml` at repo root wiring together:
  - All mock services, MCP servers, the AI Chat API, and both frontend apps.
  - Environment variable overrides for local development (no real Azure needed for mock data paths).
- Add a `docker-compose.test.yml` for running the full pytest + Vitest suites inside containers.

**Testable outcome:** `docker compose up` brings up all services; `docker compose -f docker-compose.test.yml run tests` passes the full test suite.

---

### Issue 16 – CI/CD GitHub Actions Pipelines

**Goal:** Automate build, test, and deploy for every push and pull request.

**Workflows to implement:**

| Workflow file | Trigger | Steps |
|---|---|---|
| `ci.yml` | PR / push to `main` | Lint (ruff), type-check (mypy / tsc), unit tests (pytest + Vitest), `az bicep build` |
| `build-push.yml` | Push to `main` | Build & push all Docker images to ACR |
| `deploy-infra.yml` | Manual / release tag | `az deployment group create` with Bicep templates |
| `deploy-apps.yml` | After `build-push.yml` | Update Container App revisions with new image tags |

**Tasks:**
- Implement all four workflow files under `.github/workflows/`.
- Use `azure/login` with Federated Identity (OIDC) — no long-lived secrets.
- Cache `uv` and `npm` dependencies for faster builds.

**Testable outcome:** All four workflows run successfully on a push to `main`; a PR triggers `ci.yml` with green status checks.

---

### Issue 17 – Observability & Security Hardening

**Goal:** Add end-to-end observability and enforce the security requirements from the architecture.

**Tasks:**
- Instrument all FastAPI apps with `azure-monitor-opentelemetry` (traces, metrics, logs).
- Add structured logging to all agents; ensure no PII or financial data is logged.
- Configure distributed tracing so a user request can be traced from the frontend through every agent hop to the backend service.
- Add a secrets-scanning step to `ci.yml` (e.g., `trufflesecurity/trufflehog`).
- Add rate limiting middleware to the AI Chat API.
- Write a short `docs/security.md` documenting the security posture.

**Testable outcome:** A test request appears as a complete distributed trace in Application Insights; `pytest` security-focused tests pass; secrets scan finds no leaks.

---

### Issue 18 – End-to-End Integration Tests

**Goal:** Validate the full three-tier flow with automated integration tests that run against the local `docker-compose` stack.

**Test scenarios to cover:**
1. User asks for account balance → Supervisor routes to Account Agent → returns mock balance.
2. User asks for last 5 transactions → Supervisor routes to Transaction Agent → returns mock list.
3. User submits a payment by amount and beneficiary → Supervisor routes to Payment Agent → payment confirmed.
4. User uploads an invoice image → Payment Agent calls ScanInvoice → invoice data extracted → payment submitted.
5. User repeats a previous payment → Payment Agent retrieves transaction history → resubmits payment.

**Tasks:**
- Implement `backend/tests/integration/test_e2e.py` using `httpx` against the running `docker-compose` stack.
- Implement `frontend/simple-chat/src/__tests__/e2e.test.tsx` (Playwright) exercising the chat UI.
- Add an `integration-tests.yml` GitHub Actions workflow that spins up `docker-compose` and runs both test suites.

**Testable outcome:** All five scenarios pass; CI workflow is green.

---

## Dependency Graph

```
Issue 1  (Scaffolding)
    ├── Issue 2  (Account Service)  ──────────────────────────────────────────────────┐
    ├── Issue 3  (Transactions Service)  ────────────────────────────────────────────┤
    ├── Issue 4  (Payments Service)  ──────────────────────────────────────────────── Issue 5 (FastMCP)
    │                                                                                    │
    ├── Issue 6  (ScanInvoice / Doc Intelligence)  ──────────────────────────────────┤
    │                                                                                    │
    │                                                                         ┌──────────▼──────────┐
    │                                                                         │  Issue 7  (Account  │
    │                                                                         │  Agent)             │
    │                                                                         │  Issue 8  (Txn      │
    │                                                                         │  Agent)             │
    │                                                                         │  Issue 9  (Payment  │
    │                                                                         │  Agent)             │
    │                                                                         └──────────┬──────────┘
    │                                                                                    │
    │                                                                         Issue 10 (Supervisor)
    │                                                                                    │
    │                                                                         Issue 11 (Chat API)
    │                                                                                    │
    ├── Issue 12 (Simple Chat UI) ──────────────────────────────────────────────────────┤
    ├── Issue 13 (Banking Web UI) ──────────────────────────────────────────────────────┤
    │                                                                                    │
    ├── Issue 14 (Bicep Infra) ──────────────────────────────────────────────── Issue 16 (CI/CD)
    └── Issue 15 (Docker / docker-compose) ─────────────────────────────────────────────┤
                                                                                         │
                                                                              Issue 17 (Observability)
                                                                                         │
                                                                              Issue 18 (E2E Tests)
```

---

## Recommended Issue Labels

| Label | Issues |
|---|---|
| `backend` | 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 |
| `frontend` | 12, 13 |
| `infra` | 14, 15, 16 |
| `agents` | 7, 8, 9, 10 |
| `mcp` | 5, 6 |
| `testing` | 17, 18 |
| `security` | 6, 17 |

---

## Notes

- **Testing-first philosophy**: every issue above ships with unit tests before the next dependent issue begins.
- **No Azure required for issues 1–13**: mock services and mocked Azure SDK calls allow full local development and CI without a live Azure subscription.
- **Issues can be parallelised**: issues 2, 3, 4, and 6 are independent and can be worked concurrently; issues 7, 8, 9 depend only on issue 5 and can also be parallelised.
- **uv** is used for all Python dependency management; **pnpm** or **npm** for frontend packages.
