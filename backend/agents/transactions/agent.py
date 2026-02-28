"""Transaction Agent – answers transaction history and search queries.

Uses the Microsoft Agent Framework (MAF) with MCP tool bindings to
the Account MCP server (API1) and the Transactions MCP server (API3).

Environment variables
---------------------
FOUNDRY_PROJECT_ENDPOINT        (required) Azure AI Foundry project endpoint.
FOUNDRY_MODEL_DEPLOYMENT_NAME   (optional) Model deployment name, default: gpt-4.1
ACCOUNT_MCP_URL                 (optional) Account MCP streamable-HTTP URL,
                                 default: http://localhost:9001/mcp/
TRANSACTIONS_MCP_URL            (optional) Transactions MCP streamable-HTTP URL,
                                 default: http://localhost:9002/mcp/
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from agent_framework import MCPStreamableHTTPTool
from agent_framework.azure import AzureOpenAIResponsesClient
from azure.identity.aio import DefaultAzureCredential

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENT_NAME = "TransactionAgent"

SYSTEM_PROMPT = """\
You are the Transaction Agent for a banking assistant.

Your responsibilities:
- Retrieve transaction history for a given account or recipient.
- Search transactions by keyword, category, or description.
- Report transaction details including amount, currency, date, and status.
- Notify or record new transaction events when requested.
- Look up account information to provide context for transactions.

Guidelines:
- Always confirm the account or recipient exists via a tool call
  before reporting details.
- Use only data returned by tools – never speculate or fabricate figures.
- Present monetary values with currency symbols and two decimal places.
- Format transaction lists clearly, one transaction per line with key fields.
- If a requested account, recipient, or transaction is not found,
  inform the user politely.
"""

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_config() -> dict:
    """Read configuration from environment variables at call time."""
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
    if not endpoint:
        raise OSError(
            "FOUNDRY_PROJECT_ENDPOINT environment variable is required."
        )
    return {
        "project_endpoint": endpoint,
        "model_deployment_name": os.environ.get(
            "FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4.1"
        ),
        "account_mcp_url": os.environ.get(
            "ACCOUNT_MCP_URL", "http://localhost:9001/mcp/"
        ),
        "transactions_mcp_url": os.environ.get(
            "TRANSACTIONS_MCP_URL", "http://localhost:9002/mcp/"
        ),
    }


def _create_mcp_tools(account_mcp_url: str, transactions_mcp_url: str) -> list:
    """Build the list of MCP tools for this agent."""
    return [
        MCPStreamableHTTPTool(
            name="AccountMCP",
            description=(
                "Account service tools: look up accounts by username, "
                "retrieve account details, payment methods, and beneficiaries."
            ),
            url=account_mcp_url,
            load_prompts=False,
        ),
        MCPStreamableHTTPTool(
            name="TransactionsMCP",
            description=(
                "Transaction service tools: search transactions, retrieve "
                "transaction history by recipient, and record new transactions."
            ),
            url=transactions_mcp_url,
            load_prompts=False,
        ),
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@asynccontextmanager
async def create_transaction_agent():
    """Async context manager that yields a ready-to-use Transaction Agent.

    Example usage::

        async with create_transaction_agent() as agent:
            result = await agent.run("Show my recent transactions.")
            print(result.text)
    """
    config = _get_config()
    tools = _create_mcp_tools(
        config["account_mcp_url"], config["transactions_mcp_url"]
    )

    async with (
        DefaultAzureCredential() as credential,
        AzureOpenAIResponsesClient(
            project_endpoint=config["project_endpoint"],
            deployment_name=config["model_deployment_name"],
            credential=credential,
        ).as_agent(
            name=AGENT_NAME,
            instructions=SYSTEM_PROMPT,
            tools=tools,
        ) as agent,
    ):
        yield agent


async def run_query(message: str, thread=None) -> str:
    """Run a single query through the Transaction Agent and return the response text.

    Parameters
    ----------
    message:
        The user message to send to the agent.
    thread:
        Optional existing conversation thread for multi-turn sessions.

    Returns
    -------
    str
        The agent's text response, or an empty string if no text was produced.
    """
    async with create_transaction_agent() as agent:
        if thread is not None:
            result = await agent.run(message, thread=thread)
        else:
            result = await agent.run(message)
        return result.text or ""
