"""Supervisor Agent – classifies user intent and routes to specialist agents.

Uses the Microsoft Agent Framework (MAF) for intent classification and
hand-off to the correct specialist agent.

Intent routing
--------------
  AccountInfo        → Account Agent
  Transactions       → Transaction Agent
  PayInvoice         → Payment Agent
  RepeatPayment      → Payment Agent

Environment variables
---------------------
FOUNDRY_PROJECT_ENDPOINT        (required) Azure AI Foundry project endpoint.
FOUNDRY_MODEL_DEPLOYMENT_NAME   (optional) Model deployment name, default: gpt-4.1
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from agent_framework.azure import AzureAIClient
from azure.identity.aio import DefaultAzureCredential

from agents.account.agent import create_account_agent
from agents.payments.agent import create_payment_agent
from agents.transactions.agent import create_transaction_agent

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENT_NAME = "SupervisorAgent"

SYSTEM_PROMPT = """\
You are the Supervisor Agent for a banking assistant. Your sole job is to
classify the user's intent and respond with ONLY the single intent label that
best matches, from the following list:

  AccountInfo       – questions about account balance, account details,
                      payment methods, or beneficiaries.
  Transactions      – questions about transaction history, past payments,
                      or searching transactions.
  PayInvoice        – requests to pay an invoice or bill from a document or URL.
  RepeatPayment     – requests to repeat or resubmit a previous payment.
  Unknown           – the request does not match any of the above.

Rules:
- Respond with ONLY the intent label and nothing else.
- Do not include punctuation, explanations, or any other text.
"""

INTENT_ACCOUNT = "AccountInfo"
INTENT_TRANSACTIONS = "Transactions"
INTENT_PAY_INVOICE = "PayInvoice"
INTENT_REPEAT_PAYMENT = "RepeatPayment"
INTENT_UNKNOWN = "Unknown"

_PAYMENT_INTENTS: frozenset[str] = frozenset(
    {INTENT_PAY_INVOICE, INTENT_REPEAT_PAYMENT}
)

_KNOWN_INTENTS: frozenset[str] = frozenset(
    {
        INTENT_ACCOUNT,
        INTENT_TRANSACTIONS,
        INTENT_PAY_INVOICE,
        INTENT_REPEAT_PAYMENT,
        INTENT_UNKNOWN,
    }
)

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
    }


def _classify_intent(text: str) -> str:
    """Extract the intent label from the classifier agent's response.

    Returns one of the known intent constants, or ``INTENT_UNKNOWN`` if the
    response text does not match any recognised label.
    """
    label = (text or "").strip()
    return label if label in _KNOWN_INTENTS else INTENT_UNKNOWN


# ---------------------------------------------------------------------------
# Supervisor wrapper
# ---------------------------------------------------------------------------


class _SupervisorAgent:
    """Wraps the MAF classifier agent and routes to registered specialist agents."""

    def __init__(
        self,
        classifier_agent,
        account_agent_factory,
        transaction_agent_factory,
        payment_agent_factory,
    ) -> None:
        self._classifier = classifier_agent
        self._account_factory = account_agent_factory
        self._transaction_factory = transaction_agent_factory
        self._payment_factory = payment_agent_factory

    async def run(self, message: str, thread=None) -> object:
        """Classify intent then hand off to the appropriate specialist agent.

        Parameters
        ----------
        message:
            The user message to classify and forward.
        thread:
            Optional conversation thread passed to the specialist agent for
            multi-turn sessions.

        Returns
        -------
        object
            The result object returned by the specialist agent (or the
            classifier result when the intent is Unknown).
        """
        # Step 1: classify intent via the supervisor LLM
        classify_result = await self._classifier.run(message)
        intent = _classify_intent(classify_result.text or "")

        # Step 2: hand off to the registered specialist agent
        if intent == INTENT_ACCOUNT:
            factory = self._account_factory
        elif intent == INTENT_TRANSACTIONS:
            factory = self._transaction_factory
        elif intent in _PAYMENT_INTENTS:
            factory = self._payment_factory
        else:
            # Unknown intent – return the classifier's response directly
            return classify_result

        async with factory() as specialist:
            if thread is not None:
                return await specialist.run(message, thread=thread)
            return await specialist.run(message)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@asynccontextmanager
async def create_supervisor_agent():
    """Async context manager that yields a ready-to-use Supervisor Agent.

    The supervisor classifies user intent and hands off to the appropriate
    registered specialist agent (Account, Transaction, or Payment).

    Example usage::

        async with create_supervisor_agent() as agent:
            result = await agent.run("Show me my balance")
            print(result.text)
    """
    config = _get_config()

    async with (
        DefaultAzureCredential() as credential,
        AzureAIClient(
            project_endpoint=config["project_endpoint"],
            model_deployment_name=config["model_deployment_name"],
            credential=credential,
        ).create_agent(
            name=AGENT_NAME,
            instructions=SYSTEM_PROMPT,
            tools=[],
        ) as classifier_agent,
    ):
        yield _SupervisorAgent(
            classifier_agent=classifier_agent,
            account_agent_factory=create_account_agent,
            transaction_agent_factory=create_transaction_agent,
            payment_agent_factory=create_payment_agent,
        )


async def run_query(message: str, thread=None) -> str:
    """Run a single query through the Supervisor Agent and return the response text.

    Parameters
    ----------
    message:
        The user message to send to the supervisor.
    thread:
        Optional existing conversation thread for multi-turn sessions.

    Returns
    -------
    str
        The specialist agent's text response, or an empty string if no text
        was produced.
    """
    async with create_supervisor_agent() as agent:
        result = await agent.run(message, thread=thread)
        return result.text or ""
