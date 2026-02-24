"""Tests for the Account Agent.

Unit tests mock the MAF AgentsClient so no Azure credentials are needed.
The integration test wires the MCP tool functions to the in-process mock
account service, validating the full tool-call path without network I/O.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

import agents.account.agent as agent_module
from agents.account.agent import (
    AccountAgent,
    getAccountByUsername,
    getAccountDetails,
    getPaymentMethods,
    getRegisteredBeneficiaries,
)
from services.account_service import app as account_app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(thread_id: str = "thread-1", status: str = "completed") -> MagicMock:
    """Build a minimal mock ThreadRun object."""
    run = MagicMock()
    run.thread_id = thread_id
    run.status = status
    return run


def _make_text_content(text: str) -> MagicMock:
    """Build a mock MessageTextContent object."""
    content = MagicMock()
    content.text = SimpleNamespace(value=text)
    return content


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def patch_mcp_http_client(monkeypatch):
    """Route account MCP tool HTTP calls to the in-process account service."""

    def mock_get_http_client() -> AsyncClient:
        return AsyncClient(
            transport=ASGITransport(app=account_app), base_url="http://test"
        )

    monkeypatch.setattr(agent_module, "_get_http_client", mock_get_http_client)


# ---------------------------------------------------------------------------
# Unit tests – AccountAgent class (MAF SDK mocked)
# ---------------------------------------------------------------------------


class TestAccountAgentInit:
    """Tests for AccountAgent initialisation and context management."""

    async def test_setup_creates_agent_with_correct_params(self):
        """create_agent must be called with the system prompt and model."""
        mock_agent = MagicMock()
        mock_agent.id = "agent-123"

        mock_client = AsyncMock()
        mock_client.create_agent = AsyncMock(return_value=mock_agent)
        mock_client.delete_agent = AsyncMock()
        mock_client.close = AsyncMock()

        with patch(
            "agents.account.agent.AgentsClient", return_value=mock_client
        ), patch(
            "agents.account.agent.DefaultAzureCredential", return_value=MagicMock()
        ):
            async with AccountAgent(endpoint="https://fake.endpoint") as agent:
                assert agent._agent_id == "agent-123"

        mock_client.create_agent.assert_called_once()
        call_kwargs = mock_client.create_agent.call_args.kwargs
        assert call_kwargs["model"] is not None
        assert "account" in call_kwargs["instructions"].lower()
        assert call_kwargs["name"] == "AccountAgent"

    async def test_teardown_deletes_agent_and_closes_client(self):
        """Exiting the context manager must delete the agent and close the client."""
        mock_agent = MagicMock()
        mock_agent.id = "agent-xyz"

        mock_client = AsyncMock()
        mock_client.create_agent = AsyncMock(return_value=mock_agent)
        mock_client.delete_agent = AsyncMock()
        mock_client.close = AsyncMock()

        with patch(
            "agents.account.agent.AgentsClient", return_value=mock_client
        ), patch(
            "agents.account.agent.DefaultAzureCredential", return_value=MagicMock()
        ):
            async with AccountAgent(endpoint="https://fake.endpoint"):
                pass

        mock_client.delete_agent.assert_called_once_with("agent-xyz")
        mock_client.close.assert_called_once()

    async def test_chat_raises_if_not_initialised(self):
        """chat() must raise RuntimeError when called outside a context manager."""
        agent = AccountAgent(
            endpoint="https://fake.endpoint", credential=MagicMock()
        )
        with pytest.raises(RuntimeError, match="async context manager"):
            await agent.chat("Hello")


class TestAccountAgentChat:
    """Tests for AccountAgent.chat()."""

    async def test_chat_returns_agent_reply(self):
        """chat() must return the last agent message text."""
        mock_agent = MagicMock()
        mock_agent.id = "agent-abc"

        expected_reply = "Your balance is $2,500.00."
        mock_run = _make_run(thread_id="thread-99")
        mock_text = _make_text_content(expected_reply)

        mock_messages = AsyncMock()
        mock_messages.get_last_message_text_by_role = AsyncMock(
            return_value=mock_text
        )

        mock_client = AsyncMock()
        mock_client.create_agent = AsyncMock(return_value=mock_agent)
        mock_client.create_thread_and_process_run = AsyncMock(return_value=mock_run)
        mock_client.delete_agent = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.messages = mock_messages

        with patch(
            "agents.account.agent.AgentsClient", return_value=mock_client
        ), patch(
            "agents.account.agent.DefaultAzureCredential", return_value=MagicMock()
        ):
            async with AccountAgent(endpoint="https://fake.endpoint") as agent:
                reply = await agent.chat("What is my balance?")

        assert reply == expected_reply

    async def test_chat_passes_user_message_in_thread(self):
        """chat() must include the user message in the thread options."""
        mock_agent = MagicMock()
        mock_agent.id = "agent-abc"

        mock_run = _make_run(thread_id="thread-99")
        mock_text = _make_text_content("Some reply")

        mock_messages = AsyncMock()
        mock_messages.get_last_message_text_by_role = AsyncMock(
            return_value=mock_text
        )

        mock_client = AsyncMock()
        mock_client.create_agent = AsyncMock(return_value=mock_agent)
        mock_client.create_thread_and_process_run = AsyncMock(return_value=mock_run)
        mock_client.delete_agent = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.messages = mock_messages

        user_msg = "Show me my payment methods."

        with patch(
            "agents.account.agent.AgentsClient", return_value=mock_client
        ), patch(
            "agents.account.agent.DefaultAzureCredential", return_value=MagicMock()
        ):
            async with AccountAgent(endpoint="https://fake.endpoint") as agent:
                await agent.chat(user_msg)

        call_kwargs = mock_client.create_thread_and_process_run.call_args.kwargs
        thread_options = call_kwargs["thread"]
        messages = thread_options["messages"]
        assert len(messages) == 1
        assert messages[0]["content"] == user_msg

    async def test_chat_returns_empty_string_when_no_reply(self):
        """chat() must return an empty string when no agent message is found."""
        mock_agent = MagicMock()
        mock_agent.id = "agent-abc"

        mock_run = _make_run(thread_id="thread-99")

        mock_messages = AsyncMock()
        mock_messages.get_last_message_text_by_role = AsyncMock(return_value=None)

        mock_client = AsyncMock()
        mock_client.create_agent = AsyncMock(return_value=mock_agent)
        mock_client.create_thread_and_process_run = AsyncMock(return_value=mock_run)
        mock_client.delete_agent = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.messages = mock_messages

        with patch(
            "agents.account.agent.AgentsClient", return_value=mock_client
        ), patch(
            "agents.account.agent.DefaultAzureCredential", return_value=MagicMock()
        ):
            async with AccountAgent(endpoint="https://fake.endpoint") as agent:
                reply = await agent.chat("Hello")

        assert reply == ""


# ---------------------------------------------------------------------------
# Integration tests – MCP tool functions against the in-process mock service
# ---------------------------------------------------------------------------


class TestMcpToolFunctions:
    """Validate that the agent's MCP tool wrappers correctly call the account service.

    The ``patch_mcp_http_client`` autouse fixture redirects all HTTP requests
    to the in-process FastAPI account_service app so no real network is needed.
    """

    async def test_getAccountByUsername_happy_path(self):
        result = await getAccountByUsername("john_doe")
        data = json.loads(result)
        assert data["username"] == "john_doe"
        assert data["account_id"] == "ACC001"
        assert "full_name" in data

    async def test_getAccountByUsername_not_found(self):
        with pytest.raises(Exception):
            await getAccountByUsername("nonexistent_user")

    async def test_getAccountDetails_happy_path(self):
        result = await getAccountDetails("ACC001")
        data = json.loads(result)
        assert data["account_id"] == "ACC001"
        assert "balance" in data
        assert "account_type" in data

    async def test_getAccountDetails_not_found(self):
        with pytest.raises(Exception):
            await getAccountDetails("INVALID")

    async def test_getPaymentMethods_happy_path(self):
        result = await getPaymentMethods("ACC001")
        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) > 0
        assert "payment_method_id" in data[0]
        assert "type" in data[0]

    async def test_getPaymentMethods_not_found(self):
        with pytest.raises(Exception):
            await getPaymentMethods("INVALID")

    async def test_getRegisteredBeneficiaries_happy_path(self):
        result = await getRegisteredBeneficiaries("ACC001")
        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) > 0
        assert "beneficiary_id" in data[0]
        assert "name" in data[0]

    async def test_getRegisteredBeneficiaries_not_found(self):
        with pytest.raises(Exception):
            await getRegisteredBeneficiaries("INVALID")
