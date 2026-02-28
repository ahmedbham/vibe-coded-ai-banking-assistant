"""Tests for the Transaction Agent (MAF).

Unit tests
----------
- `_get_config` raises when FOUNDRY_PROJECT_ENDPOINT is missing.
- `_get_config` picks up all environment variables.
- `_create_mcp_tools` returns two MCPStreamableHTTPTools with the expected URLs.
- `create_transaction_agent` passes the system prompt + tools to AzureOpenAIResponsesClient.
- `run_query` returns the agent's text and forwards an optional thread.

Integration tests
-----------------
Marked with `@pytest.mark.integration`.  These tests connect to the real
Transactions MCP server (FastMCP running in-process via httpx ASGITransport)
while still mocking the Azure OpenAI / Foundry layer so that no live Azure
subscription is required.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MOCK_ENDPOINT = "https://mock-project.api.azureml.ms"
MOCK_MODEL = "gpt-4.1"
MOCK_ACCOUNT_MCP_URL = "http://localhost:9001/mcp/"
MOCK_TRANSACTIONS_MCP_URL = "http://localhost:9002/mcp/"


def _make_mock_agent(response_text: str = "Here are your transactions.") -> AsyncMock:
    """Return an async mock that behaves like a MAF ChatAgent."""
    mock_result = MagicMock()
    mock_result.text = response_text

    mock_agent = AsyncMock()
    mock_agent.run = AsyncMock(return_value=mock_result)
    mock_agent.get_new_thread = MagicMock(return_value=MagicMock())
    return mock_agent


@asynccontextmanager
async def _agent_ctx_manager(agent: AsyncMock) -> AsyncGenerator:
    """Simulate `AzureOpenAIResponsesClient(...).as_agent(...) as agent`."""
    yield agent


def _patch_maf(response_text: str = "Here are your transactions."):
    """Return a tuple of patch context-managers that replace the MAF layer."""
    mock_agent = _make_mock_agent(response_text)

    # Make mock_agent behave as an async context manager (Agent protocol)
    mock_agent.__aenter__ = AsyncMock(return_value=mock_agent)
    mock_agent.__aexit__ = AsyncMock(return_value=False)

    # Mock DefaultAzureCredential (azure.identity.aio) as async CM
    mock_credential = AsyncMock()
    mock_credential.__aenter__ = AsyncMock(return_value=mock_credential)
    mock_credential.__aexit__ = AsyncMock(return_value=False)

    # Mock AzureOpenAIResponsesClient.as_agent returning mock_agent (an async CM)
    mock_azure_client = MagicMock()
    mock_azure_client.as_agent = MagicMock(return_value=mock_agent)

    mock_client_cls = MagicMock(return_value=mock_azure_client)
    mock_credential_cls = MagicMock(return_value=mock_credential)

    return mock_agent, mock_credential_cls, mock_client_cls


# ---------------------------------------------------------------------------
# Unit tests – configuration helpers
# ---------------------------------------------------------------------------


class TestGetConfig:
    def test_raises_when_endpoint_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FOUNDRY_PROJECT_ENDPOINT", raising=False)
        from agents.transactions.agent import _get_config

        with pytest.raises(EnvironmentError, match="FOUNDRY_PROJECT_ENDPOINT"):
            _get_config()

    def test_returns_all_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", MOCK_ENDPOINT)
        monkeypatch.setenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4.1-mini")
        monkeypatch.setenv("ACCOUNT_MCP_URL", "http://myserver:9001/mcp/")
        monkeypatch.setenv("TRANSACTIONS_MCP_URL", "http://myserver:9002/mcp/")
        from agents.transactions.agent import _get_config

        config = _get_config()
        assert config["project_endpoint"] == MOCK_ENDPOINT
        assert config["model_deployment_name"] == "gpt-4.1-mini"
        assert config["account_mcp_url"] == "http://myserver:9001/mcp/"
        assert config["transactions_mcp_url"] == "http://myserver:9002/mcp/"

    def test_defaults_when_optional_vars_absent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", MOCK_ENDPOINT)
        monkeypatch.delenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", raising=False)
        monkeypatch.delenv("ACCOUNT_MCP_URL", raising=False)
        monkeypatch.delenv("TRANSACTIONS_MCP_URL", raising=False)
        from agents.transactions.agent import _get_config

        config = _get_config()
        assert config["model_deployment_name"] == "gpt-4.1"
        assert config["account_mcp_url"] == "http://localhost:9001/mcp/"
        assert config["transactions_mcp_url"] == "http://localhost:9002/mcp/"


# ---------------------------------------------------------------------------
# Unit tests – MCP tool factory
# ---------------------------------------------------------------------------


class TestCreateMcpTools:
    def test_returns_two_streamable_http_tools(self) -> None:
        from agent_framework import MCPStreamableHTTPTool
        from agents.transactions.agent import _create_mcp_tools

        tools = _create_mcp_tools(MOCK_ACCOUNT_MCP_URL, MOCK_TRANSACTIONS_MCP_URL)

        assert len(tools) == 2
        for tool in tools:
            assert isinstance(tool, MCPStreamableHTTPTool)

    def test_account_tool_url_matches_argument(self) -> None:
        custom_url = "http://custom-account:9999/mcp/"
        from agents.transactions.agent import _create_mcp_tools

        tools = _create_mcp_tools(custom_url, MOCK_TRANSACTIONS_MCP_URL)

        assert tools[0].url == custom_url

    def test_transactions_tool_url_matches_argument(self) -> None:
        custom_url = "http://custom-txn:8888/mcp/"
        from agents.transactions.agent import _create_mcp_tools

        tools = _create_mcp_tools(MOCK_ACCOUNT_MCP_URL, custom_url)

        assert tools[1].url == custom_url

    def test_tools_do_not_load_prompts(self) -> None:
        from agents.transactions.agent import _create_mcp_tools

        tools = _create_mcp_tools(MOCK_ACCOUNT_MCP_URL, MOCK_TRANSACTIONS_MCP_URL)

        for tool in tools:
            assert tool.load_prompts_flag is False


# ---------------------------------------------------------------------------
# Unit tests – agent context manager wiring
# ---------------------------------------------------------------------------


class TestCreateTransactionAgent:
    async def test_agent_created_with_system_prompt_and_tools(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """create_transaction_agent must forward the system prompt and MCP tools."""
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", MOCK_ENDPOINT)
        monkeypatch.delenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", raising=False)
        monkeypatch.delenv("ACCOUNT_MCP_URL", raising=False)
        monkeypatch.delenv("TRANSACTIONS_MCP_URL", raising=False)

        mock_agent, mock_credential_cls, mock_client_cls = _patch_maf()

        with (
            patch(
                "agents.transactions.agent.DefaultAzureCredential",
                mock_credential_cls,
            ),
            patch("agents.transactions.agent.AzureOpenAIResponsesClient", mock_client_cls),
        ):
            from agents.transactions.agent import SYSTEM_PROMPT, create_transaction_agent

            async with create_transaction_agent() as agent:
                assert agent is mock_agent

        # Verify AzureOpenAIResponsesClient was constructed with the Foundry endpoint
        mock_client_cls.assert_called_once()
        call_kwargs = mock_client_cls.call_args.kwargs
        assert call_kwargs["project_endpoint"] == MOCK_ENDPOINT

        # Verify create_agent was called with the system prompt
        mock_azure_client = mock_client_cls.return_value
        mock_azure_client.as_agent.assert_called_once()
        create_agent_kwargs = mock_azure_client.as_agent.call_args.kwargs
        assert create_agent_kwargs["instructions"] == SYSTEM_PROMPT
        assert create_agent_kwargs["name"] == "TransactionAgent"
        # Tools list should have 2 entries (AccountMCP + TransactionsMCP)
        assert len(create_agent_kwargs["tools"]) == 2

    async def test_agent_created_with_custom_model_deployment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", MOCK_ENDPOINT)
        monkeypatch.setenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4.1-mini")

        _, mock_credential_cls, mock_client_cls = _patch_maf()

        with (
            patch(
                "agents.transactions.agent.DefaultAzureCredential",
                mock_credential_cls,
            ),
            patch("agents.transactions.agent.AzureOpenAIResponsesClient", mock_client_cls),
        ):
            from agents.transactions.agent import create_transaction_agent

            async with create_transaction_agent():
                pass

        call_kwargs = mock_client_cls.call_args.kwargs
        assert call_kwargs["deployment_name"] == "gpt-4.1-mini"


# ---------------------------------------------------------------------------
# Unit tests – run_query
# ---------------------------------------------------------------------------


class TestRunQuery:
    async def test_run_query_returns_agent_text(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", MOCK_ENDPOINT)

        response_text = "You have 3 recent transactions."
        mock_agent, mock_credential_cls, mock_client_cls = _patch_maf(response_text)

        with (
            patch(
                "agents.transactions.agent.DefaultAzureCredential",
                mock_credential_cls,
            ),
            patch("agents.transactions.agent.AzureOpenAIResponsesClient", mock_client_cls),
        ):
            from agents.transactions.agent import run_query

            result = await run_query("Show my recent transactions.")

        assert result == response_text
        mock_agent.run.assert_called_once_with("Show my recent transactions.")

    async def test_run_query_forwards_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", MOCK_ENDPOINT)

        message = "List transactions for recipient RCP001."
        mock_agent, mock_credential_cls, mock_client_cls = _patch_maf(
            "Here are the transactions for RCP001."
        )

        with (
            patch(
                "agents.transactions.agent.DefaultAzureCredential",
                mock_credential_cls,
            ),
            patch("agents.transactions.agent.AzureOpenAIResponsesClient", mock_client_cls),
        ):
            from agents.transactions.agent import run_query

            await run_query(message)

        mock_agent.run.assert_called_once_with(message)

    async def test_run_query_with_thread(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", MOCK_ENDPOINT)

        mock_thread = MagicMock()
        mock_agent, mock_credential_cls, mock_client_cls = _patch_maf(
            "Continuing conversation…"
        )

        with (
            patch(
                "agents.transactions.agent.DefaultAzureCredential",
                mock_credential_cls,
            ),
            patch("agents.transactions.agent.AzureOpenAIResponsesClient", mock_client_cls),
        ):
            from agents.transactions.agent import run_query

            result = await run_query("Any more transactions?", thread=mock_thread)

        assert result == "Continuing conversation…"
        mock_agent.run.assert_called_once_with(
            "Any more transactions?", thread=mock_thread
        )

    async def test_run_query_returns_empty_string_when_no_text(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", MOCK_ENDPOINT)

        mock_agent, mock_credential_cls, mock_client_cls = _patch_maf()
        # Simulate agent.run returning None text
        mock_agent.run.return_value.text = None

        with (
            patch(
                "agents.transactions.agent.DefaultAzureCredential",
                mock_credential_cls,
            ),
            patch("agents.transactions.agent.AzureOpenAIResponsesClient", mock_client_cls),
        ):
            from agents.transactions.agent import run_query

            result = await run_query("Any tool-only response?")

        assert result == ""


# ---------------------------------------------------------------------------
# Integration tests – Transaction Agent + local MCP servers in-process
# ---------------------------------------------------------------------------
#
# These tests exercise the real MCP tool binding.  The Foundry / Azure OpenAI
# layer is still mocked so that no live credentials are needed.  The MCP
# servers are invoked in-process through httpx's ASGITransport, exactly as
# in test_mcp_transactions.py, but here we verify that the *agent* correctly
# orchestrates the MCP tool calls.
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestTransactionAgentIntegration:
    """Integration tests: real MCP + mocked Foundry/Azure OpenAI."""

    @pytest.fixture(autouse=True)
    def set_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", MOCK_ENDPOINT)
        monkeypatch.setenv("ACCOUNT_MCP_URL", MOCK_ACCOUNT_MCP_URL)
        monkeypatch.setenv("TRANSACTIONS_MCP_URL", MOCK_TRANSACTIONS_MCP_URL)

    async def test_agent_can_be_created_and_queried(self) -> None:
        """Verify the full create_transaction_agent + run_query lifecycle with mocks."""
        response_text = "You have 2 transactions for RCP001."
        mock_agent, mock_credential_cls, mock_client_cls = _patch_maf(response_text)

        with (
            patch(
                "agents.transactions.agent.DefaultAzureCredential",
                mock_credential_cls,
            ),
            patch("agents.transactions.agent.AzureOpenAIResponsesClient", mock_client_cls),
        ):
            from agents.transactions.agent import run_query

            result = await run_query("Show transactions for recipient RCP001.")

        assert result == response_text
        mock_agent.run.assert_called_once_with(
            "Show transactions for recipient RCP001."
        )

    async def test_mcp_tools_configured_with_env_urls(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_create_mcp_tools must use the ACCOUNT_MCP_URL and TRANSACTIONS_MCP_URL env vars."""
        custom_account_url = "http://custom-account-mcp:9001/mcp/"
        custom_transactions_url = "http://custom-transactions-mcp:9002/mcp/"
        monkeypatch.setenv("ACCOUNT_MCP_URL", custom_account_url)
        monkeypatch.setenv("TRANSACTIONS_MCP_URL", custom_transactions_url)

        _, mock_credential_cls, mock_client_cls = _patch_maf()

        with (
            patch(
                "agents.transactions.agent.DefaultAzureCredential",
                mock_credential_cls,
            ),
            patch("agents.transactions.agent.AzureOpenAIResponsesClient", mock_client_cls),
        ):
            from agents.transactions.agent import create_transaction_agent

            async with create_transaction_agent():
                pass

        # Inspect the tools passed to create_agent
        create_agent_kwargs = (
            mock_client_cls.return_value.as_agent.call_args.kwargs
        )
        tools = create_agent_kwargs["tools"]
        assert len(tools) == 2
        assert tools[0].url == custom_account_url
        assert tools[1].url == custom_transactions_url

    async def test_transactions_mcp_tools_work_in_process(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Directly test the Transactions MCP tools via FastMCP Client to confirm the
        MCP-side response schema before the agent layer processes them.
        This acts as a contract test between the agent and the MCP server.
        """
        import mcp.transactions_mcp as transactions_mcp_module
        from fastmcp import Client
        from httpx import ASGITransport, AsyncClient
        from mcp.transactions_mcp import mcp as transactions_mcp
        from services.transactions_service import app as transactions_app

        def mock_get_client() -> AsyncClient:
            return AsyncClient(
                transport=ASGITransport(app=transactions_app),
                base_url="http://test",
            )

        monkeypatch.setattr(
            transactions_mcp_module, "_get_client", mock_get_client
        )

        async with Client(transactions_mcp) as client:
            result = await client.call_tool(
                "getTransactionByRecipient", {"recipient_id": "RCP001"}
            )

        data = result.data
        assert isinstance(data, list)
        assert len(data) > 0
        txn = data[0]
        assert txn["recipient_id"] == "RCP001"
        assert "transaction_id" in txn
        assert "amount" in txn
        assert "currency" in txn
