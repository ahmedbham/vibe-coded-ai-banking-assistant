"""Account Agent – Microsoft Agent Framework (MAF) implementation.

The agent is backed by Azure AI Agents (azure-ai-agents) and exposes the
account service capabilities via AsyncFunctionTool wrappers that call the
Account MCP server.

Configuration via environment variables:
  AZURE_AI_AGENT_ENDPOINT   – Azure AI Projects / Foundry endpoint URL
  AZURE_OPENAI_DEPLOYMENT   – Model deployment name (default: gpt-4.1)
  ACCOUNT_MCP_URL           – Base URL of the Account MCP server
                              (default: http://localhost:9001)

Usage::

    from agents.account.agent import AccountAgent

    async with AccountAgent() as agent:
        reply = await agent.chat("What is my account balance?")
        print(reply)
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
from azure.ai.agents.aio import AgentsClient
from azure.ai.agents.models import (
    AgentThreadCreationOptions,
    AsyncFunctionTool,
    AsyncToolSet,
    MessageRole,
    ThreadMessageOptions,
)
from azure.identity.aio import DefaultAzureCredential

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AZURE_AI_AGENT_ENDPOINT: str = os.getenv("AZURE_AI_AGENT_ENDPOINT", "")
MODEL: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1")
ACCOUNT_MCP_URL: str = os.getenv("ACCOUNT_MCP_URL", "http://localhost:9001")

AGENT_NAME = "AccountAgent"
SYSTEM_PROMPT = (
    "You are a helpful banking account assistant. "
    "You can look up account information, check credit balances, "
    "retrieve account details, list payment methods, and show "
    "registered beneficiaries. "
    "Always be concise and accurate when presenting financial information. "
    "Only answer questions related to account information; "
    "politely decline unrelated requests."
)

# ---------------------------------------------------------------------------
# MCP tool wrappers (called as async function tools by the MAF agent)
# ---------------------------------------------------------------------------


def _get_http_client() -> httpx.AsyncClient:
    """Return an httpx async client pointed at the Account MCP HTTP server."""
    return httpx.AsyncClient(base_url=ACCOUNT_MCP_URL)


async def getAccountByUsername(username: str) -> str:
    """Return account information for the given username.

    :param username: The username to look up.
    :type username: str
    :return: JSON-encoded account information dict.
    :rtype: str
    """
    async with _get_http_client() as client:
        response = await client.get(f"/accounts/{username}")
        response.raise_for_status()
        return json.dumps(response.json())


async def getAccountDetails(account_id: str) -> str:
    """Return detailed account information for the given account ID.

    Returns balance, account type, currency, and status.

    :param account_id: The account ID to look up.
    :type account_id: str
    :return: JSON-encoded account details dict.
    :rtype: str
    """
    async with _get_http_client() as client:
        response = await client.get(f"/accounts/{account_id}/details")
        response.raise_for_status()
        return json.dumps(response.json())


async def getPaymentMethods(account_id: str) -> str:
    """Return the list of payment methods registered for the given account ID.

    :param account_id: The account ID to query.
    :type account_id: str
    :return: JSON-encoded list of payment method dicts.
    :rtype: str
    """
    async with _get_http_client() as client:
        response = await client.get(f"/accounts/{account_id}/payment-methods")
        response.raise_for_status()
        return json.dumps(response.json())


async def getRegisteredBeneficiaries(account_id: str) -> str:
    """Return the list of registered beneficiaries for the given account ID.

    :param account_id: The account ID to query.
    :type account_id: str
    :return: JSON-encoded list of beneficiary dicts.
    :rtype: str
    """
    async with _get_http_client() as client:
        response = await client.get(f"/accounts/{account_id}/beneficiaries")
        response.raise_for_status()
        return json.dumps(response.json())


# ---------------------------------------------------------------------------
# AccountAgent
# ---------------------------------------------------------------------------


class AccountAgent:
    """Async context-manager wrapper around the MAF AgentsClient.

    Example::

        async with AccountAgent() as agent:
            reply = await agent.chat("What is my balance for ACC001?")
    """

    def __init__(
        self,
        *,
        endpoint: str | None = None,
        model: str | None = None,
        credential: Any = None,
    ) -> None:
        self._endpoint = endpoint or AZURE_AI_AGENT_ENDPOINT
        self._model = model or MODEL
        self._credential = credential or DefaultAzureCredential()
        self._client: AgentsClient | None = None
        self._agent_id: str | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _create_toolset() -> AsyncToolSet:
        """Build an AsyncToolSet with all account MCP tool wrappers."""
        toolset = AsyncToolSet()
        toolset.add(
            AsyncFunctionTool(
                {
                    getAccountByUsername,
                    getAccountDetails,
                    getPaymentMethods,
                    getRegisteredBeneficiaries,
                }
            )
        )
        return toolset

    # ------------------------------------------------------------------
    # Context-manager helpers
    # ------------------------------------------------------------------

    async def __aenter__(self) -> AccountAgent:
        await self._setup()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self._teardown()

    # ------------------------------------------------------------------
    # Internal setup / teardown
    # ------------------------------------------------------------------

    async def _setup(self) -> None:
        """Create the AgentsClient and register the agent definition."""
        self._client = AgentsClient(
            endpoint=self._endpoint,
            credential=self._credential,
        )

        agent = await self._client.create_agent(
            model=self._model,
            name=AGENT_NAME,
            instructions=SYSTEM_PROMPT,
            toolset=self._create_toolset(),
        )
        self._agent_id = agent.id

    async def _teardown(self) -> None:
        """Delete the ephemeral agent and close the client."""
        if self._client is not None:
            if self._agent_id:
                await self._client.delete_agent(self._agent_id)
                self._agent_id = None
            await self._client.close()
            self._client = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def chat(self, user_message: str) -> str:
        """Send a message to the agent and return the text reply.

        :param user_message: The user's input message.
        :type user_message: str
        :return: The agent's text response.
        :rtype: str
        :raises RuntimeError: If the agent has not been initialised
            (use as async context manager).
        """
        if self._client is None or self._agent_id is None:
            raise RuntimeError(
                "AccountAgent must be used as an async context manager. "
                "Use `async with AccountAgent() as agent:`"
            )

        thread_options = AgentThreadCreationOptions(
            messages=[
                ThreadMessageOptions(
                    role=MessageRole.USER,
                    content=user_message,
                )
            ]
        )

        run = await self._client.create_thread_and_process_run(
            agent_id=self._agent_id,
            thread=thread_options,
            toolset=self._create_toolset(),
        )

        last_msg = await self._client.messages.get_last_message_text_by_role(
            thread_id=run.thread_id,
            role=MessageRole.AGENT,
        )
        return last_msg.text.value if last_msg and last_msg.text else ""
