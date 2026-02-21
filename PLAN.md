# PLAN.md – Multi-Agent Banking Assistant: Build Plan

This document breaks the three-tier multi-agent banking assistant (see [`docs/architecture.md`](docs/architecture.md)) into a series of logical, independently testable GitHub Issues. Each issue produces a runnable, verifiable increment so it can be assigned, reviewed, and tested in isolation before the next step begins.

**Incremental Provisioning Principle:** Every issue that builds a component destined for Azure is immediately followed by a paired issue that provisions the required Azure resources, deploys the component, and validates the deployment. This ensures infrastructure is grown incrementally alongside the application rather than in one large batch at the end.

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

### Issue 2 – Base Azure Infrastructure

**Goal:** Provision the shared Azure resources that all subsequent components will depend on. This foundation must exist before any component is deployed to Azure.

**Azure resources to provision:**
- Azure Resource Group (environment-specific, e.g. `rg-banking-dev`).
- Azure Container Registry (ACR) for all container images.
- Azure Container Apps Environment (shared across all Container Apps).
- Azure Key Vault for secrets management.
- Azure Monitor workspace + Application Insights instance.
- User-assigned Managed Identity with base role assignments (ACR pull, Key Vault Secrets User).

**Tasks:**
- Implement `infra/modules/container-registry.bicep`, `infra/modules/container-apps-env.bicep`, `infra/modules/key-vault.bicep`, `infra/modules/monitor.bicep`, `infra/modules/managed-identity.bicep`.
- Implement `infra/main.bicep` composing all modules; parameterise `environment`, `location`, `project`, and `owner` tags on every resource.
- Add `infra/parameters.dev.json` with dev-environment defaults.
- Add `scripts/deploy-base-infra.sh` that runs `az deployment group create` and prints resource endpoints.
- Validate templates with `az bicep build --file infra/main.bicep` in CI.
- Run `az deployment group what-if` against a test subscription before applying.

**Testable outcome:** `az bicep build --file infra/main.bicep` succeeds; `scripts/deploy-base-infra.sh` provisions all resources in a test resource group without errors; ACR login succeeds from a local workstation.

---

### Issue 3 – Mock Account Service (Backend Tier)

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

### Issue 4 – Containerize & Deploy Account Service to Azure Container Apps

**Goal:** Package the Account Service as a Docker image, push it to ACR, and deploy it as a Container App. Validate the live deployment end-to-end.

**Tasks:**
- Finalise the multi-stage `backend/Dockerfile` to produce a minimal, non-root image for the Account Service.
- Add `infra/modules/container-app-account-service.bicep` defining the Container App (image, port, environment variables, Managed Identity binding).
- Extend `infra/main.bicep` to include the new module (using the `existing` keyword for shared resources).
- Add `scripts/deploy-account-service.sh` that builds and pushes the image to ACR then runs `az deployment group create`.
- Run `az deployment group what-if` before applying.
- Smoke-test the deployed endpoint: `curl https://<fqdn>/accounts/john_doe` returns the expected mock JSON.

**Testable outcome:** Container App is running in Azure; `GET /accounts/john_doe` against the live URL returns mock account data; `az bicep build` succeeds on the updated `infra/main.bicep`.

---

### Issue 5 – Mock Transactions (Reporting) Service (Backend Tier)

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

### Issue 6 – Containerize & Deploy Transactions Service to Azure Container Apps

**Goal:** Package the Transactions Service as a Docker image and deploy it as a Container App, mirroring the pattern from Issue 4.

**Tasks:**
- Add `infra/modules/container-app-transactions-service.bicep` defining the Container App.
- Extend `infra/main.bicep` with the new module.
- Add `scripts/deploy-transactions-service.sh` (build → push → deploy).
- Run `az deployment group what-if` before applying.
- Smoke-test: `GET /transactions/search?query=coffee` against the live URL returns mock results.

**Testable outcome:** Transactions Service Container App is running in Azure; live smoke tests pass; `az bicep build` succeeds.

---

### Issue 7 – Mock Payments Service (Backend Tier)

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

### Issue 8 – Containerize & Deploy Payments Service to Azure Container Apps

**Goal:** Package the Payments Service as a Docker image and deploy it as a Container App.

**Tasks:**
- Add `infra/modules/container-app-payments-service.bicep` defining the Container App.
- Extend `infra/main.bicep` with the new module.
- Add `scripts/deploy-payments-service.sh` (build → push → deploy).
- Run `az deployment group what-if` before applying.
- Smoke-test: `POST /payments` against the live URL returns a payment confirmation ID.

**Testable outcome:** Payments Service Container App is running in Azure; live smoke tests pass; `az bicep build` succeeds.

---

### Issue 9 – FastMCP Layer (Backend Tier)

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

### Issue 10 – Containerize & Deploy FastMCP Servers to Azure Container Apps

**Goal:** Package and deploy all three FastMCP servers (Account, Transactions, Payments) as Container Apps, pointing each at its already-deployed backend service.

**Tasks:**
- Add `infra/modules/container-app-account-mcp.bicep`, `container-app-transactions-mcp.bicep`, `container-app-payments-mcp.bicep`.
- Configure each MCP Container App with the environment variable pointing to the corresponding backend service URL (resolved from deployed Container App FQDNs).
- Extend `infra/main.bicep` with the three new modules.
- Add `scripts/deploy-mcp-servers.sh` (build → push → deploy all three).
- Run `az deployment group what-if` before applying.
- Smoke-test each MCP tool endpoint against the live URLs; confirm tool responses match mock data.

**Testable outcome:** All three MCP Container Apps are running in Azure; tool-call smoke tests pass against live endpoints; `az bicep build` succeeds.

---

### Issue 11 – Azure Document Intelligence Integration (ScanInvoice Tool)

**Goal:** Add the `ScanInvoice` MCP tool used by the Payment Agent to extract invoice data from uploaded images/PDFs using Azure Document Intelligence.

**Tasks:**
- Implement `backend/mcp/document_mcp.py` wrapping the Azure Document Intelligence `prebuilt-invoice` model.
- Use `DefaultAzureCredential` for authentication; accept the endpoint via environment variable `DOCUMENT_INTELLIGENCE_ENDPOINT`.
- Expose a `scanInvoice(file_url: str) -> InvoiceData` MCP tool returning extracted fields (vendor, amount, due date, etc.).
- Add unit tests using `pytest` + `unittest.mock` to mock the Azure SDK calls and verify field extraction logic.
- Document required Azure resource setup in a `docs/setup-document-intelligence.md` file.

**Testable outcome:** `pytest backend/tests/test_document_mcp.py` passes with mocked Azure SDK.

---

### Issue 12 – Provision Azure Document Intelligence & Deploy Document MCP to Azure

**Goal:** Provision an Azure Document Intelligence resource and deploy the Document MCP server as a Container App, then validate real invoice extraction end-to-end.

**Tasks:**
- Add `infra/modules/document-intelligence.bicep` defining the Cognitive Services account (`kind: FormRecognizer`).
- Add `infra/modules/container-app-document-mcp.bicep` with the `DOCUMENT_INTELLIGENCE_ENDPOINT` environment variable sourced from the Bicep output.
- Extend `infra/main.bicep` with the two new modules; grant the Managed Identity `Cognitive Services User` role on the Document Intelligence resource.
- Add `scripts/deploy-document-mcp.sh` (provision resource → build image → push → deploy Container App).
- Run `az deployment group what-if` before applying.
- Integration test: call `scanInvoice` against the live MCP endpoint with a sample invoice PDF; verify extracted fields.

**Testable outcome:** Document Intelligence resource is provisioned; `scanInvoice` MCP tool returns real extracted data from a sample invoice against the live Azure endpoint; `az bicep build` succeeds.

---

### Issue 13 – Account Agent (Middle Tier)

**Goal:** Implement the **Account Agent** using the Microsoft Agent Framework (MAF), bound to the Account Service MCP tools.

**Tasks:**
- Implement `backend/agents/account/agent.py` using MAF, configured with:
  - System prompt scoped to account information, credit balance, and payment methods.
  - MCP tool binding to `account_mcp` (URL configurable via environment variable).
  - GPT-4.1 via Azure OpenAI (`DefaultAzureCredential`).
- Add unit tests in `backend/tests/test_account_agent.py` mocking the MAF SDK and MCP tool calls.
- Add an integration test that runs the agent against the local mock MCP server (Issue 9).

**Testable outcome:** `pytest backend/tests/test_account_agent.py` passes; running the agent locally returns account info for a mock user.

---

### Issue 14 – Transaction Agent (Middle Tier)

**Goal:** Implement the **Transaction Agent** using MAF, bound to the Account and Transactions MCP tools.

**Tasks:**
- Implement `backend/agents/transactions/agent.py` using MAF, configured with:
  - System prompt scoped to transaction history queries.
  - MCP tool bindings to `account_mcp` (API1) and `transactions_mcp` (API3).
  - GPT-4.1 via Azure OpenAI.
- Add unit and integration tests in `backend/tests/test_transaction_agent.py`.

**Testable outcome:** `pytest backend/tests/test_transaction_agent.py` passes; agent returns a formatted list of mock transactions.

---

### Issue 15 – Payment Agent (Middle Tier)

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

### Issue 16 – Supervisor Agent (Middle Tier)

**Goal:** Implement the **Supervisor Agent** using MAF to triage user messages and hand off to the correct specialist agent.

**Tasks:**
- Implement `backend/agents/supervisor/agent.py` using MAF with the hand-off pattern:
  - Intent routing: `AccountInfo` → Account Agent, `Transactions` → Transaction Agent, `PayInvoice` / `RepeatPayment` → Payment Agent.
  - GPT-4.1 system prompt for intent classification and response synthesis.
- Register all three specialist agents as hand-off targets.
- Add unit tests validating routing logic and integration tests validating end-to-end hand-off with mock agents.

**Testable outcome:** `pytest backend/tests/test_supervisor_agent.py` passes; "Show me my balance" is routed to the Account Agent; "Pay my electricity bill" is routed to the Payment Agent.

---

### Issue 17 – Provision Azure AI Foundry & Deploy Agents to Foundry Agent Service

**Goal:** Provision the Azure AI Foundry project, Azure OpenAI resource, and Foundry Agent Service deployment, then deploy all four agents and validate end-to-end routing in Azure.

**Azure resources to provision:**
- Azure AI Foundry Hub + Project.
- Azure OpenAI resource with GPT-4.1 model deployment.
- Foundry Agent Service deployment for all four agents (Supervisor, Account, Transaction, Payment).

**Tasks:**
- Add `infra/modules/ai-foundry.bicep` (Hub + Project).
- Add `infra/modules/openai.bicep` (Azure OpenAI resource + GPT-4.1 deployment).
- Add `infra/modules/foundry-agent-service.bicep` referencing all four agent definitions.
- Grant the Managed Identity `Cognitive Services OpenAI User` and `Azure AI Developer` roles.
- Extend `infra/main.bicep` with all new modules.
- Add `scripts/deploy-agents.sh` that provisions resources and registers agents on Foundry Agent Service.
- Run `az deployment group what-if` before applying.
- Integration test: send a "Show me my balance" prompt to the deployed Supervisor Agent; confirm it routes to the Account Agent and returns real mock-service data via the live MCP servers.

**Testable outcome:** All four agents are registered on Foundry Agent Service; end-to-end routing test passes against Azure; `az bicep build` succeeds.

---

### Issue 18 – AI Chat API (Middle Tier FastAPI)

**Goal:** Expose a single `/chat` HTTP endpoint that fronts the Supervisor Agent and returns streaming responses.

**Tasks:**
- Implement `backend/api/chat.py` as a FastAPI router:
  - `POST /chat` accepts `{ "message": str, "session_id": str }` and returns a streaming response.
  - Authenticated with Azure Managed Identity (`DefaultAzureCredential`).
  - Instrumented with Azure Monitor OpenTelemetry.
- Wire all agents and MCP servers together in `backend/main.py`.
- Add `pytest` tests for the `/chat` endpoint using `httpx.AsyncClient` with mocked agent responses.
- Add a `docker-compose.yml` at the repo root for local end-to-end development (all services + MCP servers + API).

**Testable outcome:** `pytest backend/tests/test_chat_api.py` passes; `curl -X POST /chat -d '{"message":"What is my balance?"}'` returns a streamed response locally.

---

### Issue 19 – Containerize & Deploy AI Chat API to Azure Container Apps

**Goal:** Package the AI Chat API as a Docker image, deploy it as a Container App, and validate streaming chat responses against the live Azure stack.

**Tasks:**
- Add `infra/modules/container-app-chat-api.bicep` with environment variables for all MCP server URLs, the Foundry Agent Service endpoint, and Application Insights connection string.
- Extend `infra/main.bicep` with the new module.
- Add `scripts/deploy-chat-api.sh` (build → push → deploy).
- Run `az deployment group what-if` before applying.
- Smoke-test: `curl -X POST https://<fqdn>/chat -d '{"message":"What is my balance?","session_id":"test"}'` returns a streamed response from the live Supervisor Agent.

**Testable outcome:** AI Chat API Container App is running in Azure; streaming chat smoke test passes against the live URL; `az bicep build` succeeds.

---

### Issue 20 – Simple Chat Frontend (`frontend/simple-chat`)

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

### Issue 21 – Containerize & Deploy Simple Chat Frontend to Azure Container Apps

**Goal:** Deploy the Simple Chat frontend as a Container App and validate the full user-facing chat flow in Azure.

**Tasks:**
- Add `infra/modules/container-app-simple-chat.bicep` with the `VITE_API_URL` build argument set to the deployed Chat API URL.
- Extend `infra/main.bicep` with the new module.
- Add `scripts/deploy-simple-chat.sh` (build → push → deploy).
- Run `az deployment group what-if` before applying.
- Smoke-test: open the deployed URL in a browser; send "What is my balance?" and verify a response appears.

**Testable outcome:** Simple Chat Container App is accessible at its Azure URL; end-to-end browser smoke test passes; `az bicep build` succeeds.

---

### Issue 22 – Full Banking Web Frontend (`frontend/banking-web`)

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

### Issue 23 – Containerize & Deploy Full Banking Web Frontend to Azure Container Apps

**Goal:** Deploy the Banking Web frontend as a Container App and validate all dashboard views against the live Azure stack.

**Tasks:**
- Add `infra/modules/container-app-banking-web.bicep` with the `VITE_API_URL` build argument and any other required environment variables.
- Extend `infra/main.bicep` with the new module.
- Add `scripts/deploy-banking-web.sh` (build → push → deploy).
- Run `az deployment group what-if` before applying.
- Smoke-test: open the deployed URL; verify the account summary, transaction table, and chat panel all render and respond correctly.

**Testable outcome:** Banking Web Container App is accessible at its Azure URL; all dashboard views render with live data; `az bicep build` succeeds.

---

### Issue 24 – Docker & Local docker-compose Setup

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

### Issue 25 – CI/CD GitHub Actions Pipelines

**Goal:** Automate build, test, and deploy for every push and pull request.

**Workflows to implement:**

| Workflow file | Trigger | Steps |
|---|---|---|
| `ci.yml` | PR / push to `main` | Lint (ruff), type-check (mypy / tsc), unit tests (pytest + Vitest), `az bicep build` |
| `build-push.yml` | Push to `main` | Build & push all Docker images to ACR |
| `deploy-infra.yml` | Manual / release tag | `az deployment group create` with Bicep templates (incremental, module by module) |
| `deploy-apps.yml` | After `build-push.yml` | Update Container App revisions with new image tags |

**Tasks:**
- Implement all four workflow files under `.github/workflows/`.
- Use `azure/login` with Federated Identity (OIDC) — no long-lived secrets.
- Cache `uv` and `npm` dependencies for faster builds.
- Each deployment job in `deploy-infra.yml` targets only the modules changed in the current release, keeping deployments incremental.

**Testable outcome:** All four workflows run successfully on a push to `main`; a PR triggers `ci.yml` with green status checks.

---

### Issue 26 – Observability & Security Hardening

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

### Issue 27 – End-to-End Integration Tests

**Goal:** Validate the full three-tier flow with automated integration tests that run against both the local `docker-compose` stack and the live Azure deployment.

**Test scenarios to cover:**
1. User asks for account balance → Supervisor routes to Account Agent → returns mock balance.
2. User asks for last 5 transactions → Supervisor routes to Transaction Agent → returns mock list.
3. User submits a payment by amount and beneficiary → Supervisor routes to Payment Agent → payment confirmed.
4. User uploads an invoice image → Payment Agent calls ScanInvoice → invoice data extracted → payment submitted.
5. User repeats a previous payment → Payment Agent retrieves transaction history → resubmits payment.

**Tasks:**
- Implement `backend/tests/integration/test_e2e.py` using `httpx` against the running `docker-compose` stack and against the live Azure Chat API URL.
- Implement `frontend/simple-chat/src/__tests__/e2e.test.tsx` (Playwright) exercising the chat UI against both local and Azure deployments.
- Add an `integration-tests.yml` GitHub Actions workflow that spins up `docker-compose` and also runs smoke tests against the deployed Azure environment.

**Testable outcome:** All five scenarios pass locally and in Azure; CI workflow is green.

---

## Dependency Graph

```
Issue 1  (Scaffolding)
    │
    └── Issue 2  (Base Azure Infra: ACR, Container Apps Env, Key Vault, Monitor)
            │
            ├── Issue 3  (Account Service – local) ──► Issue 4  (Deploy Account Service → Azure)
            │
            ├── Issue 5  (Transactions Service – local) ──► Issue 6  (Deploy Transactions Service → Azure)
            │
            ├── Issue 7  (Payments Service – local) ──► Issue 8  (Deploy Payments Service → Azure)
            │
            │   [Issues 4, 6, 8 must complete before Issue 9]
            │
            ├── Issue 9  (FastMCP Layer – local) ──► Issue 10 (Deploy FastMCP Servers → Azure)
            │
            ├── Issue 11 (ScanInvoice / Doc Intelligence – local) ──► Issue 12 (Provision Doc Intelligence + Deploy Doc MCP → Azure)
            │
            │   [Issues 10, 12 must complete before Issue 17]
            │
            ├── Issue 13 (Account Agent – local)    ─┐
            ├── Issue 14 (Transaction Agent – local) ─┤──► Issue 17 (Provision AI Foundry + Deploy Agents → Azure)
            ├── Issue 15 (Payment Agent – local)    ─┤
            └── Issue 16 (Supervisor Agent – local) ─┘
                                                        │
                                                    Issue 18 (AI Chat API – local) ──► Issue 19 (Deploy Chat API → Azure)
                                                                                            │
                                                                            ┌───────────────┘
                                                                            │
                                                        Issue 20 (Simple Chat UI – local) ──► Issue 21 (Deploy Simple Chat → Azure)
                                                        Issue 22 (Banking Web UI – local) ──► Issue 23 (Deploy Banking Web → Azure)
                                                                            │
                                                                    Issue 24 (Docker / docker-compose)
                                                                            │
                                                                    Issue 25 (CI/CD)
                                                                            │
                                                                    Issue 26 (Observability)
                                                                            │
                                                                    Issue 27 (E2E Tests)
```

---

## Recommended Issue Labels

| Label | Issues |
|---|---|
| `backend` | 3, 5, 7, 9, 11, 13, 14, 15, 16, 18 |
| `frontend` | 20, 22 |
| `infra` | 2, 4, 6, 8, 10, 12, 17, 19, 21, 23, 24, 25 |
| `agents` | 13, 14, 15, 16, 17 |
| `mcp` | 9, 10, 11, 12 |
| `testing` | 26, 27 |
| `security` | 11, 26 |

---

## Notes

- **Incremental Azure provisioning**: every component-building issue is paired with an immediately following Azure provisioning/deployment/validation issue. Infrastructure grows alongside the application.
- **Testing-first philosophy**: every application issue ships with unit tests before the next dependent issue begins.
- **No Azure required for odd-numbered issues 3–22**: mock services and mocked Azure SDK calls allow full local development and CI without a live Azure subscription.
- **Even-numbered issues 4–23 require Azure**: these are the paired provisioning/deployment issues and need an active Azure subscription with OIDC credentials configured in the `dev` GitHub Actions Environment.
- **Issues can be parallelised**: issues 3, 5, 7 are independent and can be worked concurrently; their paired deployment issues (4, 6, 8) can also run in parallel once Issue 2 is complete; issues 13, 14, 15, 16 depend only on issue 10 and 12, and can be parallelised.
- **Bicep modularity**: each new Azure resource gets its own Bicep module in `infra/modules/`. The `existing` keyword is used in child modules to reference shared resources provisioned in Issue 2.
- **uv** is used for all Python dependency management; **pnpm** or **npm** for frontend packages.
