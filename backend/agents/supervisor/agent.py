"""Supervisor Agent – triage and hand-off orchestration via MAF HandoffBuilder.

Uses the Microsoft Agent Framework (MAF) Handoff Orchestration with Autonomous
Mode to route user messages to the correct specialist agent without requiring
human-in-the-loop interaction.

Intent routing (via triage agent's system prompt)
--------------------------------------------------
  Account / balance / payment-method queries  → Account Agent
  Transaction history / search queries         → Transaction Agent
  Pay-invoice / repeat-payment requests        → Payment Agent

Architecture
------------
The supervisor is built with ``HandoffBuilder`` and three specialist agents,
all backed by ``AzureOpenAIChatClient`` with the appropriate MCP tool bindings.
Autonomous mode (``with_autonomous_mode()``) is enabled so the workflow
completes without waiting for human input after each specialist turn.

Environment variables
---------------------
AZURE_OPENAI_ENDPOINT           (required) Azure OpenAI service endpoint URL.
FOUNDRY_MODEL_DEPLOYMENT_NAME   (optional) Model deployment name, default: gpt-4.1
ACCOUNT_MCP_URL                 (optional) Account MCP URL, default: http://localhost:9001/mcp/
PAYMENTS_MCP_URL                (optional) Payments MCP URL, default: http://localhost:9003/mcp/
TRANSACTIONS_MCP_URL            (optional) Transactions MCP URL, default: http://localhost:9002/mcp/
DOCUMENT_MCP_URL                (optional) Document MCP URL, default: http://localhost:9004/mcp/
"""

from __future__ import annotations

import os

from agent_framework import MCPStreamableHTTPTool
from agent_framework.azure import AzureOpenAIChatClient
from agent_framework.orchestrations import HandoffBuilder
from azure.identity import DefaultAzureCredential

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPERVISOR_NAME = "supervisor_agent"
ACCOUNT_AGENT_NAME = "account_agent"
TRANSACTION_AGENT_NAME = "transaction_agent"
PAYMENT_AGENT_NAME = "payment_agent"

SUPERVISOR_SYSTEM_PROMPT = """\
You are the Supervisor Agent for a banking assistant. Your job is to triage
the user's request and route it to the correct specialist agent by calling
the appropriate handoff tool. ALWAYS hand off to a specialist – never answer
directly.

Routing rules:
- Questions about account balance, account details, payment methods, or
  beneficiaries → hand off to account_agent.
- Questions about transaction history, past payments, or searching
  transactions → hand off to transaction_agent.
- Requests to pay an invoice/bill or repeat a previous payment → hand off
  to payment_agent.
"""

ACCOUNT_AGENT_SYSTEM_PROMPT = """\
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

TRANSACTION_AGENT_SYSTEM_PROMPT = """\
You are the Transaction Agent for a banking assistant.

Your responsibilities:
- Retrieve transaction history for a given account or recipient.
- Search transactions by keyword, category, or description.
- Report transaction details including amount, currency, date, and status.
- Notify or record new transaction events when requested.
- Look up account information to provide context for transactions.

Guidelines:
- Always confirm the account or recipient exists via a tool call before
  reporting details.
- Use only data returned by tools – never speculate or fabricate figures.
- Present monetary values with currency symbols and two decimal places.
- Format transaction lists clearly, one transaction per line.
- If a requested account, recipient, or transaction is not found, inform
  the user politely.
"""

PAYMENT_AGENT_SYSTEM_PROMPT = """\
You are the Payment Agent for a banking assistant.

Your responsibilities:
- Submit payments on behalf of a customer (PayInvoice or RepeatPayment).
- PayInvoice: scan an invoice image/PDF via the document tool, extract the
  amount and beneficiary details, then submit via the payments tool.
- RepeatPayment: look up a previous payment in transaction history and
  resubmit it via the payments tool.
- Use the account tool to verify account details and available balance.

Guidelines:
- Always verify the account exists and has sufficient balance before
  submitting.
- Use only data returned by tools – never speculate or fabricate figures.
- Do not reveal full card numbers or authentication credentials.
- Present monetary values with currency symbols and two decimal places.
- Confirm the payment reference and status after submission.
- If a requested account, beneficiary, or invoice is not found, inform the
  user politely.
"""

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_config() -> dict:
    """Read configuration from environment variables at call time."""
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    if not endpoint:
        raise OSError(
            "AZURE_OPENAI_ENDPOINT environment variable is required."
        )
    return {
        "azure_openai_endpoint": endpoint,
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


def _build_workflow(config: dict):
    """Build the HandoffBuilder workflow with all specialist agents.

    Creates three specialist agents with their respective MCP tool bindings and
    a supervisor (triage) agent, then assembles them into a HandoffBuilder
    workflow running in autonomous mode.

    Parameters
    ----------
    config:
        Configuration dict as returned by ``_get_config()``.

    Returns
    -------
    Workflow
        A fully configured MAF Workflow ready to run.
    """
    credential = DefaultAzureCredential()
    chat_client = AzureOpenAIChatClient(
        endpoint=config["azure_openai_endpoint"],
        deployment_name=config["model_deployment_name"],
        credential=credential,
    )

    # Supervisor / triage agent – no tools; routes via handoff tool calls
    supervisor = chat_client.as_agent(
        name=SUPERVISOR_NAME,
        instructions=SUPERVISOR_SYSTEM_PROMPT,
    )

    # Account specialist agent
    account_agent = chat_client.as_agent(
        name=ACCOUNT_AGENT_NAME,
        instructions=ACCOUNT_AGENT_SYSTEM_PROMPT,
        tools=[
            MCPStreamableHTTPTool(
                name="AccountMCP",
                description=(
                    "Account service tools: look up accounts by username, "
                    "retrieve account details, payment methods, and beneficiaries."
                ),
                url=config["account_mcp_url"],
                load_prompts=False,
            )
        ],
    )

    # Transaction specialist agent
    transaction_agent = chat_client.as_agent(
        name=TRANSACTION_AGENT_NAME,
        instructions=TRANSACTION_AGENT_SYSTEM_PROMPT,
        tools=[
            MCPStreamableHTTPTool(
                name="AccountMCP",
                description=(
                    "Account service tools: look up accounts by username, "
                    "retrieve account details, payment methods, and beneficiaries."
                ),
                url=config["account_mcp_url"],
                load_prompts=False,
            ),
            MCPStreamableHTTPTool(
                name="TransactionsMCP",
                description=(
                    "Transaction service tools: search transactions, retrieve "
                    "transaction history by recipient, and record new transactions."
                ),
                url=config["transactions_mcp_url"],
                load_prompts=False,
            ),
        ],
    )

    # Payment specialist agent
    payment_agent = chat_client.as_agent(
        name=PAYMENT_AGENT_NAME,
        instructions=PAYMENT_AGENT_SYSTEM_PROMPT,
        tools=[
            MCPStreamableHTTPTool(
                name="AccountMCP",
                description=(
                    "Account service tools: look up accounts by username, "
                    "retrieve account details, payment methods, and beneficiaries."
                ),
                url=config["account_mcp_url"],
                load_prompts=False,
            ),
            MCPStreamableHTTPTool(
                name="PaymentsMCP",
                description=(
                    "Payments service tools: submit payments and "
                    "retrieve payment status."
                ),
                url=config["payments_mcp_url"],
                load_prompts=False,
            ),
            MCPStreamableHTTPTool(
                name="TransactionsMCP",
                description=(
                    "Transactions service tools: search transaction history "
                    "and look up past payments by recipient."
                ),
                url=config["transactions_mcp_url"],
                load_prompts=False,
            ),
            MCPStreamableHTTPTool(
                name="DocumentMCP",
                description=(
                    "Document service tools: scan invoices and extract structured "
                    "payment information such as vendor name, amount, and due date."
                ),
                url=config["document_mcp_url"],
                load_prompts=False,
            ),
        ],
    )

    return (
        HandoffBuilder(
            name="banking_supervisor",
            participants=[supervisor, account_agent, transaction_agent, payment_agent],
        )
        .with_start_agent(supervisor)
        .with_autonomous_mode()
        .build()
    )


def _extract_response_text(outputs: list) -> str:
    """Extract the last assistant message text from workflow outputs.

    Parameters
    ----------
    outputs:
        List of outputs from ``WorkflowRunResult.get_outputs()``.  Each item
        is a ``list[ChatMessage]`` representing the cleaned conversation.

    Returns
    -------
    str
        Text of the last assistant message, or an empty string if none found.
    """
    if not outputs:
        return ""
    conversation = outputs[-1]
    for msg in reversed(conversation):
        if msg.role == "assistant" and msg.text:
            return msg.text
    return ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def run_query(message: str) -> str:
    """Run a single query through the Supervisor Agent and return the response text.

    Builds a HandoffBuilder workflow with autonomous mode, runs the user
    message through the supervisor triage agent, which hands off to the
    appropriate specialist agent, and returns the final text response.

    Parameters
    ----------
    message:
        The user message to send to the supervisor.

    Returns
    -------
    str
        The specialist agent's text response, or an empty string if no text
        was produced.
    """
    config = _get_config()
    workflow = _build_workflow(config)
    result = await workflow.run(message)
    return _extract_response_text(result.get_outputs())
