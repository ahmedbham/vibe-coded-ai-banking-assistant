"""Account Agent – answers account and payment-method enquiries.

Uses the Microsoft Agent Framework (MAF) with an MCP tool binding to
the Account MCP server (FastMCP, running on port 9001 by default).

Environment variables
---------------------
FOUNDRY_PROJECT_ENDPOINT        (required) Azure AI Foundry project endpoint.
FOUNDRY_MODEL_DEPLOYMENT_NAME   (optional) Model deployment name, default: gpt-4.1
ACCOUNT_MCP_URL                 (optional) Account MCP streamable-HTTP URL,
                                 default: http://localhost:9001/mcp/
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from agent_framework import MCPStreamableHTTPTool
from agent_framework.azure import AzureAIClient
from azure.identity.aio import DefaultAzureCredential

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENT_NAME = "AccountAgent"

SYSTEM_PROMPT = """\
You are the Account Agent for a banking assistant.

Your responsibilities:
- Look up account information for a customer by their username or account ID.
- Report current balance, account status, type, and currency.
- List all payment methods registered on an account.
- List all registered beneficiaries for an account.
- Answer questions about credit balance or account standing.

Guidelines:
- Always confirm the account exists via a tool call before reporting details.
- Use only data returned by tools – never speculate or fabricate figures.
- Do not reveal full card numbers or authentication credentials.
- Present monetary values with currency symbols and two decimal places.
- If a requested account or resource is not found, inform the user politely.
"""

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_config() -> dict:
    """Read configuration from environment variables at call time."""
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
    if not endpoint:
        raise EnvironmentError(
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
    }


def _create_mcp_tools(account_mcp_url: str) -> list:
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
        )
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@asynccontextmanager
async def create_account_agent():
    """Async context manager that yields a ready-to-use Account Agent.

    Example usage::

        async with create_account_agent() as agent:
            result = await agent.run("What is my balance?")
            print(result.text)
    """
    config = _get_config()
    tools = _create_mcp_tools(config["account_mcp_url"])

    async with (
        DefaultAzureCredential() as credential,
        AzureAIClient(
            project_endpoint=config["project_endpoint"],
            model_deployment_name=config["model_deployment_name"],
            credential=credential,
        ).create_agent(
            name=AGENT_NAME,
            instructions=SYSTEM_PROMPT,
            tools=tools,
        ) as agent,
    ):
        yield agent


async def run_query(message: str, thread=None) -> str:
    """Run a single query through the Account Agent and return the response text.

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
    async with create_account_agent() as agent:
        if thread is not None:
            result = await agent.run(message, thread=thread)
        else:
            result = await agent.run(message)
        return result.text or ""
