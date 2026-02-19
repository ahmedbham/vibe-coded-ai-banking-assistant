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

## Tech Stack

- **Python 3.11+** · FastAPI · Uvicorn
- **Microsoft Agent Framework (MAF)** · Azure OpenAI GPT-4.1
- **Azure** – Container Apps, Foundry Agent Service, Document Intelligence, Monitor
- **React 18** · TypeScript · Vite · shadcn/ui · Tailwind CSS
- **Bicep** – Infrastructure as Code
