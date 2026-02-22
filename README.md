# vibe-coded-ai-banking-assistant

Vibe-coded Multi-agent banking assistant built with Python and the Microsoft Agent Framework (MAF), deployed on Azure Container Apps and Microsoft Foundry.

## Repository Layout

```
.
├── .github/workflows/      # GitHub Actions CI/CD workflows
├── backend/
│   ├── agents/
│   │   ├── supervisor/     # Orchestrator agent
│   │   ├── account/        # Account-information agent
│   │   ├── transactions/   # Transactions agent
│   │   └── payments/       # Payments agent
│   ├── mcp/                # MCP tool definitions (fastmcp)
│   ├── api/                # FastAPI routers
│   ├── services/           # Shared service helpers
│   ├── tests/              # pytest test suite
│   ├── pyproject.toml      # uv-managed Python dependencies
│   └── Dockerfile          # Multi-stage, non-root container image
├── frontend/
│   ├── banking-web/        # React + TypeScript banking UI
│   └── simple-chat/        # Lightweight chat interface
├── infra/                  # Bicep IaC templates
└── docs/                   # Project documentation
```

## Getting Started

### Backend

```bash
# Create a virtual environment and install dependencies
cd backend
pip install uv
uv venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv pip install ".[dev]"

# Run tests
pytest

# Lint
ruff check .
```

### Docker

```bash
cd backend
docker build -t banking-assistant-backend .
```

## GitHub Actions – Authorizing Copilot Workflow Runs

When GitHub Copilot coding agent opens a pull request or pushes to a `copilot/**` branch, GitHub Actions workflows must be authorized to run without requiring manual owner approval.  This repository uses a dedicated **`copilot`** GitHub Actions Environment (with no required reviewers) so that Copilot-triggered workflow runs proceed automatically.

### One-time setup (repository owner)

1. **Create the `copilot` environment**
   - Navigate to **Settings → Environments → New environment**.
   - Name it exactly **`copilot`**.
   - Do **not** add any required reviewers or wait timers.
   - Save the environment.

2. **Allow Copilot workflow runs** *(if not already set)*
   - Navigate to **Settings → Actions → General**.
   - Under *"Fork pull request workflows from outside collaborators"* choose at minimum **"Approve first-time contributors"** (or less restrictive).
   - Under *"Workflow permissions"* select **"Read and write permissions"** if workflows need to write back to the repository.
   - Save.

3. *(Optional)* Set the repository variable **`GH_ACTIONS_ENVIRONMENT`** to `copilot` under **Settings → Secrets and variables → Actions → Variables** to make all workflow jobs use this environment by default.

Once the `copilot` environment exists without protection rules, every workflow job that references `environment: copilot` (or `environment: ${{ vars.GH_ACTIONS_ENVIRONMENT || 'copilot' }}`) will run automatically for Copilot-triggered events.

## Tech Stack

- **Python 3.11+** · FastAPI · Uvicorn
- **Microsoft Agent Framework (MAF)** · Azure OpenAI GPT-4.1
- **Azure** – Container Apps, Foundry Agent Service, Document Intelligence, Monitor
- **React 18** · TypeScript · Vite · shadcn/ui · Tailwind CSS
- **Bicep** – Infrastructure as Code
