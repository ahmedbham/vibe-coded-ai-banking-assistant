# GitHub Copilot Coding Agent Instructions

## Project Overview

This repository is a **Multi-agent Banking Assistant** built with Python and the Microsoft Agent Framework (MAF). The assistant is deployed to **Microsoft Foundry** using the Foundry Agent Service, and application components run on **Azure Container Apps**. All code is generated and maintained by GitHub Copilot Coding Agent.

---

## Technical Stack

### Backend Technologies

#### Core Framework
- **Python 3.11+**: Primary programming language. Use modern Python features (type hints, dataclasses, `match` statements, etc.).
- **FastAPI**: Modern web framework for building APIs with automatic OpenAPI documentation. Prefer `async` route handlers.
- **Uvicorn**: Lightning-fast ASGI server implementation. Use as the production server for FastAPI apps.

#### AI & Agent Framework
- **Microsoft Agent Framework (MAF)**: Core framework for building and orchestrating agents.
- **Azure OpenAI (GPT-4.1)**: Large language model powering agent intelligence. Use via the MAF SDK; do not call the Azure OpenAI REST API directly.

#### Azure Services Integration
- **Azure Identity**: Authentication and authorization with Azure services. Always use `DefaultAzureCredential` for credential management; never hard-code secrets.
- **Azure Storage Blob**: Document and file storage.
- **Azure Document Intelligence**: OCR and invoice/receipt data extraction.
- **Azure Monitor OpenTelemetry**: Observability and telemetry. Instrument all agents and API endpoints.

### Frontend Technologies

#### Primary Frontend
- **React 18.2+**: Modern UI library.
- **TypeScript**: All frontend code must be TypeScript; avoid `any` types.
- **Vite**: Frontend build tool.
- **shadcn/ui**: Re-usable component library. Use its components as the first choice before writing custom ones.
  - **Radix UI**: Accessible component primitives (bundled with shadcn/ui).
  - **Tailwind CSS**: Utility-first CSS framework for all styling.

### Infrastructure & DevOps

#### Cloud Platform
- **Azure Container Apps**: Serverless container hosting for all application services.
- **Microsoft Foundry** (formerly Azure AI Foundry): AI model deployment and management.
  - **Foundry Agent Service**: Deploy and run all AI agents here.
- **Azure Cognitive Services**: AI capabilities such as Document Intelligence.
- **Azure Monitor & Application Insights**: Observability and monitoring for all deployed components.

#### Infrastructure as Code
- **Bicep**: All Azure infrastructure must be defined as Bicep templates. Do not use ARM JSON templates.
- **Azure Developer CLI (azd)**: Use for local development and provisioning of Azure resources.
- **Docker**: Multi-stage Dockerfiles for all services to minimise image size.
- **Azure CLI (`az`)**: Used for initial Azure resource provisioning scripts.
- **GitHub CLI (`gh`)**: Used for GitHub repository operations.

#### CI/CD
- **GitHub Actions**: Automate all CI/CD pipelines.
  - Infrastructure deployment: Bicep templates deployed via workflow.
  - Application build & deploy: Container images built and pushed to Azure Container Registry, then deployed to Azure Container Apps.

#### Build Tools
- **uv**: Fast Python package installer and resolver. Use `uv` for all Python dependency management (`uv pip`, `uv venv`, `pyproject.toml`).
- **npm / pnpm**: Package management for frontend projects (simple-chat, banking-web).

### Communication Protocols

- **Model Context Protocol (MCP)**: Expose business APIs as agent tools using [fastmcp](https://gofastmcp.com/). Prefer MCP-based tool exposure over custom plugin approaches.

---

## Architecture Guidelines

1. **Agent-first design**: Model every banking capability (balance enquiry, transfers, statement retrieval, fraud alerts, etc.) as an agent tool exposed via MCP.
2. **Multi-agent orchestration**: Use MAF to compose specialised agents (e.g. account agent, payment agent, document agent) under a top-level orchestrator agent.
3. **Security**: Never log PII or financial data. Use Azure Managed Identities for all service-to-service authentication.
4. **Observability**: Emit structured telemetry (traces, metrics, logs) to Azure Monitor from every agent and API endpoint.
5. **Stateless services**: Keep API and agent services stateless; persist state in Azure Storage or a database.
6. **Container hygiene**: Each service gets its own Dockerfile. Use non-root users in containers.

---

## Coding Conventions

### Python
- Follow **PEP 8** and **PEP 257** (docstrings).
- Use **type hints** on all function signatures.
- Manage dependencies with `pyproject.toml` + `uv`.
- Write unit tests with **pytest**; aim for high coverage of business logic.
- Use `async`/`await` throughout; avoid blocking I/O in async contexts.
- Raise domain-specific exceptions; never swallow exceptions silently.

### TypeScript / React
- Strict TypeScript (`"strict": true` in `tsconfig.json`).
- Functional components with hooks; avoid class components.
- Co-locate component tests with the component file (`*.test.tsx`).
- Use Tailwind utility classes for styling; avoid inline `style` props.

### Infrastructure (Bicep)
- Parameterise all environment-specific values.
- Use modules to organise resources logically.
- Tag every resource with at minimum `environment`, `project`, and `owner` tags.
- **Bicep Modularity**: Always break infrastructure into reusable modules in the `/infra/modules` directory.
- **Incremental Resource Discovery**: When adding a new resource that depends on an existing one, use the `existing` keyword in Bicep rather than redeclaring the full resource.
- **Pre-flight Check**: For every infrastructure change, generate an Azure "What-If" command (`az deployment group what-if`) to validate the impact before applying.

---

## Repository Structure (target)

```
.
├── .github/
│   ├── copilot-instructions.md   # This file
│   └── workflows/                # GitHub Actions workflows
├── infra/                        # Bicep IaC templates
├── backend/                      # FastAPI + MAF agent services
│   ├── agents/                   # Individual agent implementations
│   ├── mcp/                      # MCP tool definitions (fastmcp)
│   ├── api/                      # FastAPI routers
│   └── Dockerfile
├── frontend/                     # React + TypeScript UI
│   ├── banking-web/
│   └── simple-chat/
└── docs/                         # Project documentation
```

---

## Do's and Don'ts

### Do
- Use `DefaultAzureCredential` for all Azure SDK authentication.
- Write `async` FastAPI endpoints.
- Define infrastructure in Bicep before writing application code that depends on it.
- Keep secrets in Azure Key Vault; reference them via environment variables at runtime.
- Add OpenTelemetry instrumentation to every new service.

### Don't
- Hard-code secrets, connection strings, or API keys in source code or committed config files.
- Use deprecated Azure SDK packages.
- Bypass type checking with `# type: ignore` or TypeScript `any` without a justified comment.
- Commit large binary files or generated build artefacts to the repository.
- Create ARM JSON templates; use Bicep instead.

---

## Incremental Delivery Pattern

- **Atomic Features**: Every GitHub Issue representing a feature must include its own Infrastructure as Code (Bicep), Application Code, and CI/CD updates.
- **The "Test-in-Cloud" Requirement**: A feature is not "Done" until it has been deployed to a development environment in Azure and verified.
- **No "Infra-Last" Planning**: Do not group all Azure resources into a single deployment task. Provision resources as they are needed by the application components.

# Copilot Coding Agent – IaC Validation Guardrails (azd + Bicep) – Environment: dev

## GitHub Actions Environment requirement
All provisioning/validation runs MUST use the GitHub Actions Environment named **dev**.
- Secrets are retrieved from **Environment secrets** (Settings → Environments → dev).
- If the environment has approval gates/protection rules, the job will not access secrets until approved. [6](https://dev.to/pwd9000/using-github-copilot-coding-agent-for-devops-automation-3f43)[3](https://bing.com/search?q=GitHub+Actions+hosted+runner+software+installed+list+ubuntu-latest+windows-latest+macos-latest)

## Goal
Provision ephemeral Azure infrastructure for validation/testing of IaC using:
- Azure Developer CLI (azd)
- Bicep deployments via Azure CLI

## Non‑negotiable guardrails
1. **Only deploy to ephemeral test resource groups** created for the current session:
   - Prefer `IAC_RG` if set.
   - Otherwise generate a new RG with prefix `copilot-iac-` and a unique suffix.
2. **Never deploy to production subscriptions or shared resource groups.**
3. **Always clean up**:
   - Use `scripts/iac-validate.sh` (create → deploy → validate → destroy).
   - Cleanup must run via `trap` even on failures (no orphan resources/cost).
4. **Use OIDC-based Azure authentication** (no long-lived secrets). [6](https://dev.to/pwd9000/using-github-copilot-coding-agent-for-devops-automation-3f43)[3](https://bing.com/search?q=GitHub+Actions+hosted+runner+software+installed+list+ubuntu-latest+windows-latest+macos-latest)
5. **Minimize log output**:
   - Avoid printing secrets or sensitive configuration.
   - Prefer `AZURE_CORE_OUTPUT=none`. [5](https://bing.com/search?q=GitHub+Copilot+Chat+mode+VS+Code+agent+mode+coding+agent+copilot+cli+documentation)

## Expected repository layout (defaults)
- Bicep template: `infra/main.bicep` (override with `BICEP_FILE`)
- Bicep parameters (optional): `infra/parameters.json` (override with `BICEP_PARAMS_FILE`)
- AZD project root contains `azure.yaml`

## How to run the validation workflow (preferred)
```bash
bash scripts/iac-validate.sh
