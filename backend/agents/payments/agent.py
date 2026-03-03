"""Payment Agent – submits payments and processes invoices.

Uses the Microsoft Agent Framework (MAF) with MCP tool bindings to the
Account, Payments, Transactions, and Document MCP servers.

Environment variables
---------------------
FOUNDRY_PROJECT_ENDPOINT        (required) Azure AI Foundry project endpoint.
FOUNDRY_MODEL_DEPLOYMENT_NAME   (optional) Model deployment name, default: gpt-4.1
ACCOUNT_MCP_URL                 (optional) Account MCP streamable-HTTP URL,
                                 default: http://localhost:9001/mcp/
PAYMENTS_MCP_URL                (optional) Payments MCP streamable-HTTP URL,
                                 default: http://localhost:9003/mcp/
TRANSACTIONS_MCP_URL            (optional) Transactions MCP streamable-HTTP URL,
                                 default: http://localhost:9002/mcp/
DOCUMENT_MCP_URL                (optional) Document MCP streamable-HTTP URL,
                                 default: http://localhost:9004/mcp/
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from agent_framework import MCPStreamableHTTPTool
from agent_framework.azure import AzureAIAgentClient
from azure.identity.aio import DefaultAzureCredential

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENT_NAME = "PaymentAgent"

SYSTEM_PROMPT = """\
You are the Payment Agent for a banking assistant.

Your responsibilities:
- Submit payments on behalf of a customer (Intent=PayInvoice or Intent=RepeatPayment).
- PayInvoice flow: scan an invoice image/PDF via the document tool, extract the amount
  and beneficiary details, then submit the payment via the payments tool.
- RepeatPayment flow: look up a previous payment in the transaction history using the
  transactions tool, then resubmit it via the payments tool.
- Use the account tool to verify account details and available
  balance before submitting.

Guidelines:
- Always verify the account exists and has sufficient balance before submitting.
- Use only data returned by tools – never speculate or fabricate figures.
- Do not reveal full card numbers or authentication credentials.
- Present monetary values with currency symbols and two decimal places.
- Confirm the payment reference and status after submission.
- If a requested account, beneficiary, or invoice is not found,
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
        "payments_mcp_url": os.environ.get(
            "PAYMENTS_MCP_URL", "http://localhost:9003/mcp/"
        ),
        "transactions_mcp_url": os.environ.get(
            "TRANSACTIONS_MCP_URL", "http://localhost:9002/mcp/"
        ),
        "document_mcp_url": os.environ.get(
            "DOCUMENT_MCP_URL", "http://localhost:9004/mcp/"
        ),
    }


def _create_mcp_tools(
    account_mcp_url: str,
    payments_mcp_url: str,
    transactions_mcp_url: str,
    document_mcp_url: str,
) -> list:
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
            name="PaymentsMCP",
            description=(
                "Payments service tools: submit payments and retrieve payment status."
            ),
            url=payments_mcp_url,
            load_prompts=False,
        ),
        MCPStreamableHTTPTool(
            name="TransactionsMCP",
            description=(
                "Transactions service tools: search transaction history "
                "and look up past payments by recipient."
            ),
            url=transactions_mcp_url,
            load_prompts=False,
        ),
        MCPStreamableHTTPTool(
            name="DocumentMCP",
            description=(
                "Document service tools: scan invoices and extract structured "
                "payment information such as vendor name, amount, and due date."
            ),
            url=document_mcp_url,
            load_prompts=False,
        ),
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@asynccontextmanager
async def create_payment_agent():
    """Async context manager that yields a ready-to-use Payment Agent.

    Example usage::

        async with create_payment_agent() as agent:
            result = await agent.run("Pay invoice at https://example.com/invoice.pdf")
            print(result.text)
    """
    config = _get_config()
    tools = _create_mcp_tools(
        config["account_mcp_url"],
        config["payments_mcp_url"],
        config["transactions_mcp_url"],
        config["document_mcp_url"],
    )

    async with (
        DefaultAzureCredential() as credential,
        AzureAIAgentClient(
            project_endpoint=config["project_endpoint"],
            model_deployment_name=config["model_deployment_name"],
            credential=credential,
        ).as_agent(
            name=AGENT_NAME,
            instructions=SYSTEM_PROMPT,
            tools=tools,
        ) as agent,
    ):
        yield agent


async def run_query(message: str, thread=None) -> str:
    """Run a single query through the Payment Agent and return the response text.

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
    async with create_payment_agent() as agent:
        if thread is not None:
            result = await agent.run(message, thread=thread)
        else:
            result = await agent.run(message)
        return result.text or ""
