"""Tests for the Payment Agent (MAF).

Unit tests
----------
- `_get_config` raises when FOUNDRY_PROJECT_ENDPOINT is missing.
- `_get_config` picks up all environment variables.
- `_get_config` uses defaults when optional vars are absent.
- `_create_mcp_tools` returns four MCPStreamableHTTPTool instances with expected URLs.
- `create_payment_agent` passes the system prompt + tools to AzureOpenAIResponsesClient.
- `run_query` returns the agent's text and forwards an optional thread.

Integration tests
-----------------
Marked with `@pytest.mark.integration`.  These tests connect to the real
Payments/Transactions MCP servers (FastMCP running in-process via httpx
ASGITransport) while still mocking the Azure OpenAI / Foundry layer so that
no live Azure subscription is required.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MOCK_ENDPOINT = "https://mock-project.api.azureml.ms"
MOCK_MODEL = "gpt-4.1"
MOCK_ACCOUNT_MCP_URL = "http://localhost:9001/mcp/"
MOCK_PAYMENTS_MCP_URL = "http://localhost:9003/mcp/"
MOCK_TRANSACTIONS_MCP_URL = "http://localhost:9002/mcp/"
MOCK_DOCUMENT_MCP_URL = "http://localhost:9004/mcp/"


def _make_mock_agent(
    response_text: str = "Payment submitted successfully.",
) -> AsyncMock:
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


def _patch_maf(response_text: str = "Payment submitted successfully."):
    """Return a tuple of patch context-managers that replace the MAF layer."""
    mock_agent = _make_mock_agent(response_text)

    # Make mock_agent behave as an async context manager (Agent protocol)
    mock_agent.__aenter__ = AsyncMock(return_value=mock_agent)
    mock_agent.__aexit__ = AsyncMock(return_value=False)

    # Mock DefaultAzureCredential (azure.identity.aio) as async CM
    mock_credential = AsyncMock()
    mock_credential.__aenter__ = AsyncMock(return_value=mock_credential)
    mock_credential.__aexit__ = AsyncMock(return_value=False)

    # Mock AzureAIAgentClient.as_agent returning mock_agent (an async CM)
    mock_azure_client = MagicMock()
    mock_azure_client.as_agent = MagicMock(return_value=mock_agent)

    mock_client_cls = MagicMock(return_value=mock_azure_client)
    mock_credential_cls = MagicMock(return_value=mock_credential)

    return mock_agent, mock_credential_cls, mock_client_cls


# ---------------------------------------------------------------------------
# Unit tests – configuration helpers
# ---------------------------------------------------------------------------


class TestGetConfig:
    def test_raises_when_endpoint_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("FOUNDRY_PROJECT_ENDPOINT", raising=False)
        from agents.payments.agent import _get_config

        with pytest.raises(EnvironmentError, match="FOUNDRY_PROJECT_ENDPOINT"):
            _get_config()

    def test_returns_all_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", MOCK_ENDPOINT)
        monkeypatch.setenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4.1-mini")
        monkeypatch.setenv("ACCOUNT_MCP_URL", "http://myserver:9001/mcp/")
        monkeypatch.setenv("PAYMENTS_MCP_URL", "http://myserver:9003/mcp/")
        monkeypatch.setenv("TRANSACTIONS_MCP_URL", "http://myserver:9002/mcp/")
        monkeypatch.setenv("DOCUMENT_MCP_URL", "http://myserver:9004/mcp/")
        from agents.payments.agent import _get_config

        config = _get_config()
        assert config["project_endpoint"] == MOCK_ENDPOINT
        assert config["model_deployment_name"] == "gpt-4.1-mini"
        assert config["account_mcp_url"] == "http://myserver:9001/mcp/"
        assert config["payments_mcp_url"] == "http://myserver:9003/mcp/"
        assert config["transactions_mcp_url"] == "http://myserver:9002/mcp/"
        assert config["document_mcp_url"] == "http://myserver:9004/mcp/"

    def test_defaults_when_optional_vars_absent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", MOCK_ENDPOINT)
        monkeypatch.delenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", raising=False)
        monkeypatch.delenv("ACCOUNT_MCP_URL", raising=False)
        monkeypatch.delenv("PAYMENTS_MCP_URL", raising=False)
        monkeypatch.delenv("TRANSACTIONS_MCP_URL", raising=False)
        monkeypatch.delenv("DOCUMENT_MCP_URL", raising=False)
        from agents.payments.agent import _get_config

        config = _get_config()
        assert config["model_deployment_name"] == "gpt-4.1"
        assert config["account_mcp_url"] == "http://localhost:9001/mcp/"
        assert config["payments_mcp_url"] == "http://localhost:9003/mcp/"
        assert config["transactions_mcp_url"] == "http://localhost:9002/mcp/"
        assert config["document_mcp_url"] == "http://localhost:9004/mcp/"


# ---------------------------------------------------------------------------
# Unit tests – MCP tool factory
# ---------------------------------------------------------------------------


class TestCreateMcpTools:
    def test_returns_four_streamable_http_tools(self) -> None:
        from agent_framework import MCPStreamableHTTPTool

        from agents.payments.agent import _create_mcp_tools

        tools = _create_mcp_tools(
            MOCK_ACCOUNT_MCP_URL,
            MOCK_PAYMENTS_MCP_URL,
            MOCK_TRANSACTIONS_MCP_URL,
            MOCK_DOCUMENT_MCP_URL,
        )

        assert len(tools) == 4
        for tool in tools:
            assert isinstance(tool, MCPStreamableHTTPTool)

    def test_tool_urls_match_arguments(self) -> None:
        from agents.payments.agent import _create_mcp_tools

        tools = _create_mcp_tools(
            MOCK_ACCOUNT_MCP_URL,
            MOCK_PAYMENTS_MCP_URL,
            MOCK_TRANSACTIONS_MCP_URL,
            MOCK_DOCUMENT_MCP_URL,
        )

        assert tools[0].url == MOCK_ACCOUNT_MCP_URL
        assert tools[1].url == MOCK_PAYMENTS_MCP_URL
        assert tools[2].url == MOCK_TRANSACTIONS_MCP_URL
        assert tools[3].url == MOCK_DOCUMENT_MCP_URL

    def test_tools_do_not_load_prompts(self) -> None:
        from agents.payments.agent import _create_mcp_tools

        tools = _create_mcp_tools(
            MOCK_ACCOUNT_MCP_URL,
            MOCK_PAYMENTS_MCP_URL,
            MOCK_TRANSACTIONS_MCP_URL,
            MOCK_DOCUMENT_MCP_URL,
        )

        for tool in tools:
            assert tool.load_prompts_flag is False


# ---------------------------------------------------------------------------
# Unit tests – agent context manager wiring
# ---------------------------------------------------------------------------


class TestCreatePaymentAgent:
    async def test_agent_created_with_system_prompt_and_tools(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """create_payment_agent must forward the system prompt and MCP tools."""
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", MOCK_ENDPOINT)
        monkeypatch.delenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", raising=False)
        monkeypatch.delenv("ACCOUNT_MCP_URL", raising=False)
        monkeypatch.delenv("PAYMENTS_MCP_URL", raising=False)
        monkeypatch.delenv("TRANSACTIONS_MCP_URL", raising=False)
        monkeypatch.delenv("DOCUMENT_MCP_URL", raising=False)

        mock_agent, mock_credential_cls, mock_client_cls = _patch_maf()

        with (
            patch("agents.payments.agent.DefaultAzureCredential", mock_credential_cls),
            patch("agents.payments.agent.AzureAIAgentClient", mock_client_cls),
        ):
            from agents.payments.agent import SYSTEM_PROMPT, create_payment_agent

            async with create_payment_agent() as agent:
                assert agent is mock_agent

        # Verify AzureAIAgentClient was constructed with the Foundry endpoint
        mock_client_cls.assert_called_once()
        call_kwargs = mock_client_cls.call_args.kwargs
        assert call_kwargs["project_endpoint"] == MOCK_ENDPOINT

        # Verify create_agent was called with the system prompt
        mock_azure_client = mock_client_cls.return_value
        mock_azure_client.as_agent.assert_called_once()
        create_agent_kwargs = mock_azure_client.as_agent.call_args.kwargs
        assert create_agent_kwargs["instructions"] == SYSTEM_PROMPT
        assert create_agent_kwargs["name"] == "PaymentAgent"
        # Tools list should have 4 entries (account, payments, transactions, document)
        assert len(create_agent_kwargs["tools"]) == 4

    async def test_agent_created_with_custom_model_deployment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", MOCK_ENDPOINT)
        monkeypatch.setenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4.1-mini")

        _, mock_credential_cls, mock_client_cls = _patch_maf()

        with (
            patch("agents.payments.agent.DefaultAzureCredential", mock_credential_cls),
            patch("agents.payments.agent.AzureAIAgentClient", mock_client_cls),
        ):
            from agents.payments.agent import create_payment_agent

            async with create_payment_agent():
                pass

        call_kwargs = mock_client_cls.call_args.kwargs
        assert call_kwargs["model_deployment_name"] == "gpt-4.1-mini"


# ---------------------------------------------------------------------------
# Unit tests – run_query
# ---------------------------------------------------------------------------


class TestRunQuery:
    async def test_run_query_returns_agent_text(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", MOCK_ENDPOINT)

        response_text = "Payment of $250.00 to ACME Corp submitted. Reference: PAY001."
        mock_agent, mock_credential_cls, mock_client_cls = _patch_maf(response_text)

        with (
            patch("agents.payments.agent.DefaultAzureCredential", mock_credential_cls),
            patch("agents.payments.agent.AzureAIAgentClient", mock_client_cls),
        ):
            from agents.payments.agent import run_query

            result = await run_query("Pay invoice at https://example.com/invoice.pdf")

        assert result == response_text
        mock_agent.run.assert_called_once_with(
            "Pay invoice at https://example.com/invoice.pdf"
        )

    async def test_run_query_forwards_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", MOCK_ENDPOINT)

        message = "Repeat my last payment to beneficiary BEN001."
        mock_agent, mock_credential_cls, mock_client_cls = _patch_maf(
            "Payment resubmitted successfully."
        )

        with (
            patch("agents.payments.agent.DefaultAzureCredential", mock_credential_cls),
            patch("agents.payments.agent.AzureAIAgentClient", mock_client_cls),
        ):
            from agents.payments.agent import run_query

            await run_query(message)

        mock_agent.run.assert_called_once_with(message)

    async def test_run_query_with_thread(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", MOCK_ENDPOINT)

        mock_thread = MagicMock()
        mock_agent, mock_credential_cls, mock_client_cls = _patch_maf(
            "Continuing payment conversation…"
        )

        with (
            patch("agents.payments.agent.DefaultAzureCredential", mock_credential_cls),
            patch("agents.payments.agent.AzureAIAgentClient", mock_client_cls),
        ):
            from agents.payments.agent import run_query

            result = await run_query("Confirm the payment amount.", thread=mock_thread)

        assert result == "Continuing payment conversation…"
        mock_agent.run.assert_called_once_with(
            "Confirm the payment amount.", thread=mock_thread
        )

    async def test_run_query_returns_empty_string_when_no_text(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", MOCK_ENDPOINT)

        mock_agent, mock_credential_cls, mock_client_cls = _patch_maf()
        mock_agent.run.return_value.text = None

        with (
            patch("agents.payments.agent.DefaultAzureCredential", mock_credential_cls),
            patch("agents.payments.agent.AzureAIAgentClient", mock_client_cls),
        ):
            from agents.payments.agent import run_query

            result = await run_query("Any tool-only response?")

        assert result == ""


# ---------------------------------------------------------------------------
# Integration tests – Payment Agent + local MCP servers in-process
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestPaymentAgentIntegration:
    """Integration tests: real MCP + mocked Foundry/Azure OpenAI."""

    @pytest.fixture(autouse=True)
    def set_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", MOCK_ENDPOINT)
        monkeypatch.setenv("ACCOUNT_MCP_URL", MOCK_ACCOUNT_MCP_URL)
        monkeypatch.setenv("PAYMENTS_MCP_URL", MOCK_PAYMENTS_MCP_URL)
        monkeypatch.setenv("TRANSACTIONS_MCP_URL", MOCK_TRANSACTIONS_MCP_URL)
        monkeypatch.setenv("DOCUMENT_MCP_URL", MOCK_DOCUMENT_MCP_URL)

    async def test_agent_can_be_created_and_queried(self) -> None:
        """Verify the full create_payment_agent + run_query lifecycle with mocks."""
        response_text = "Payment of $500.00 to ACME Corp submitted successfully."
        mock_agent, mock_credential_cls, mock_client_cls = _patch_maf(response_text)

        with (
            patch("agents.payments.agent.DefaultAzureCredential", mock_credential_cls),
            patch("agents.payments.agent.AzureAIAgentClient", mock_client_cls),
        ):
            from agents.payments.agent import run_query

            result = await run_query(
                "Pay invoice at https://example.com/invoice.pdf for account ACC001."
            )

        assert result == response_text
        mock_agent.run.assert_called_once_with(
            "Pay invoice at https://example.com/invoice.pdf for account ACC001."
        )

    async def test_mcp_tools_configured_with_correct_urls(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """create_payment_agent must configure all 4 MCP tools with their URLs."""
        custom_account = "http://custom-account:9001/mcp/"
        custom_payments = "http://custom-payments:9003/mcp/"
        custom_transactions = "http://custom-transactions:9002/mcp/"
        custom_document = "http://custom-document:9004/mcp/"

        monkeypatch.setenv("ACCOUNT_MCP_URL", custom_account)
        monkeypatch.setenv("PAYMENTS_MCP_URL", custom_payments)
        monkeypatch.setenv("TRANSACTIONS_MCP_URL", custom_transactions)
        monkeypatch.setenv("DOCUMENT_MCP_URL", custom_document)

        _, mock_credential_cls, mock_client_cls = _patch_maf()

        with (
            patch("agents.payments.agent.DefaultAzureCredential", mock_credential_cls),
            patch("agents.payments.agent.AzureAIAgentClient", mock_client_cls),
        ):
            from agents.payments.agent import create_payment_agent

            async with create_payment_agent():
                pass

        create_agent_kwargs = (
            mock_client_cls.return_value.as_agent.call_args.kwargs
        )
        tools = create_agent_kwargs["tools"]
        assert tools[0].url == custom_account
        assert tools[1].url == custom_payments
        assert tools[2].url == custom_transactions
        assert tools[3].url == custom_document

    async def test_payments_mcp_submit_payment_in_process(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Directly test the Payments MCP tool via FastMCP Client in-process.

        This acts as a contract test verifying the MCP tool schema before
        the agent layer processes it.
        """
        from fastmcp import Client
        from httpx import ASGITransport, AsyncClient

        import mcp.payments_mcp as payments_mcp_module
        from mcp.payments_mcp import mcp as payments_mcp
        from services.payments_service import app as payments_app

        def mock_get_client() -> AsyncClient:
            return AsyncClient(
                transport=ASGITransport(app=payments_app),
                base_url="http://test",
            )

        monkeypatch.setattr(payments_mcp_module, "_get_client", mock_get_client)

        async with Client(payments_mcp) as client:
            result = await client.call_tool(
                "submitPayment",
                {
                    "account_id": "ACC001",
                    "beneficiary_id": "BEN001",
                    "amount": 250.00,
                    "currency": "USD",
                    "reference": "INV-2024-001",
                },
            )

        data = result.data
        assert data["account_id"] == "ACC001"
        assert data["beneficiary_id"] == "BEN001"
        assert data["amount"] == 250.00
        assert data["currency"] == "USD"
        assert data["reference"] == "INV-2024-001"
        assert "payment_id" in data
        assert "status" in data
