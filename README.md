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

When the GitHub Copilot coding agent opens a pull request or pushes to a `copilot/**` branch, GitHub treats it as an outside-collaborator/bot actor and holds every triggered workflow run behind an **"Approve and run"** gate until a maintainer clicks the button.

This repository addresses the problem at two levels:

| Layer | Mechanism | What it solves |
|-------|-----------|----------------|
| **Workflow run gate** | `auto-approve-copilot.yml` workflow | Approves the pending run automatically so all jobs can start |
| **Environment deployment gate** | `copilot` environment (no required reviewers) | Allows individual jobs that reference `environment: copilot` to proceed without a second human approval |

### Approach 1 – Auto-approve workflow (recommended, in-repo solution)

The file `.github/workflows/auto-approve-copilot.yml` is already committed.  It runs **from the default branch** (trusted context) and uses two triggers:

1. **`workflow_run / requested`** — fires immediately when one of the named CI workflows is requested; approves the run if the actor is `Copilot` or `copilot[bot]`.
2. **`schedule` (every 30 min)** — fallback poll that finds any remaining `action_required` runs from Copilot and approves them.

#### One-time secret setup (repository owner)

Create a fine-grained or classic Personal Access Token and store it as a repository secret:

1. Go to **GitHub → Settings (personal) → Developer settings → Personal access tokens**.
2. Create a token with at minimum:
   - **Actions: Read and write** (fine-grained), or
   - **`repo` + `workflow`** scopes (classic token).
3. Navigate to the repository **Settings → Secrets and variables → Actions → Secrets**.
4. Create a new repository secret named **`COPILOT_AUTO_APPROVE_TOKEN`** and paste the token.

> Without this secret the workflow falls back to `GITHUB_TOKEN`, which may not have sufficient permissions to approve runs from bot actors.  Setting the secret is strongly recommended.

---

### Approach 2 – `COPILOT_MCP_GITHUB_PERSONAL_ACCESS_TOKEN` (MCP-based)

If the Copilot coding agent is configured with the GitHub MCP server, you can give it a PAT so it can trigger `workflow_dispatch` jobs **as you** (the token owner).  Workflows triggered this way are logged under your identity and bypass the "Approve and run" gate entirely.

1. Create a PAT with `actions:write` (and `repo` for private repos).
2. Store it as a repository secret named **`COPILOT_MCP_GITHUB_PERSONAL_ACCESS_TOKEN`**.

Copilot will automatically pick up this secret when it runs MCP tools, and can trigger `workflow_dispatch` workflows without requiring approval.

> **Note:** This only covers workflows triggered via `workflow_dispatch`; push- and pull_request-triggered runs still use Approach 1.

---

### Approach 3 – `copilot` GitHub Actions Environment (environment gate)

This solves the *environment deployment gate* (different from the initial workflow run gate):

1. **Create the `copilot` environment**
   - Navigate to **Settings → Environments → New environment**.
   - Name it exactly **`copilot`**.
   - Do **not** add any required reviewers or wait timers.
   - Save the environment.

2. **Allow Copilot workflow runs** *(repository-level setting)*
   - Navigate to **Settings → Actions → General**.
   - Under *"Fork pull request workflows from outside collaborators"* choose at minimum **"Approve first-time contributors"** (or less restrictive).
   - Under *"Workflow permissions"* select **"Read and write permissions"** if workflows need to write back to the repository.
   - Save.

3. *(Optional)* Set the repository variable **`GH_ACTIONS_ENVIRONMENT`** to `copilot` under **Settings → Secrets and variables → Actions → Variables** to make all workflow jobs use this environment by default.

All three workflows (`ci.yml`, `validate-infra.yml`, `copilot-setup-steps.yml`) already reference `environment: copilot` (or the variable fallback), so once the environment exists without protection rules the jobs proceed automatically.

---

### Summary of required one-time owner actions

| Action | Required for |
|--------|-------------|
| Create `COPILOT_AUTO_APPROVE_TOKEN` secret (PAT with `actions:write`) | Approach 1 — auto-approve workflow run gate |
| Create `copilot` environment with no required reviewers | Approach 3 — environment deployment gate |
| Set Actions → General → "Fork PR workflows" to "Approve first-time contributors" | All approaches — reduces initial approval prompts |
| *(Optional)* Create `COPILOT_MCP_GITHUB_PERSONAL_ACCESS_TOKEN` secret | Approach 2 — MCP-dispatched workflows |

## Tech Stack

- **Python 3.11+** · FastAPI · Uvicorn
- **Microsoft Agent Framework (MAF)** · Azure OpenAI GPT-4.1
- **Azure** – Container Apps, Foundry Agent Service, Document Intelligence, Monitor
- **React 18** · TypeScript · Vite · shadcn/ui · Tailwind CSS
- **Bicep** – Infrastructure as Code
