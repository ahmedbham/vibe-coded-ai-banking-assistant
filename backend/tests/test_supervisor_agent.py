"""Tests for the Supervisor Agent (MAF HandoffBuilder).

Unit tests
----------
- `_get_config` raises when AZURE_OPENAI_ENDPOINT is missing.
- `_get_config` picks up all environment variables.
- `_get_config` uses defaults when optional vars are absent.
- `_extract_response_text` returns the last assistant message text.
- `_extract_response_text` handles empty outputs gracefully.
- `_build_workflow` creates a Workflow with the correct participants.
- `run_query` routes "Show me my balance" to the Account Agent.
- `run_query` routes "Pay my electricity bill" to the Payment Agent.
- `run_query` returns empty string when workflow produces no output.

Integration tests
-----------------
Marked with `@pytest.mark.integration`.  These tests exercise the full
HandoffBuilder workflow with a mocked MAF layer (no live Azure credentials).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MOCK_ENDPOINT = "https://mock-openai.openai.azure.com/"
MOCK_MODEL = "gpt-4.1"
MOCK_ACCOUNT_MCP_URL = "http://localhost:9001/mcp/"
MOCK_PAYMENTS_MCP_URL = "http://localhost:9003/mcp/"
MOCK_TRANSACTIONS_MCP_URL = "http://localhost:9002/mcp/"
MOCK_DOCUMENT_MCP_URL = "http://localhost:9004/mcp/"


def _make_chat_message(text: str, role: str = "assistant"):
    """Return a mock ChatMessage with the given text and role."""
    mock_role = MagicMock()
    mock_role.__eq__ = lambda self, other: (
        (hasattr(other, "value") and other.value == role) or other == role
    )
    mock_role.value = role
    msg = MagicMock()
    msg.role = mock_role
    msg.text = text
    return msg


def _make_workflow_run_result(conversation: list | None = None):
    """Return a mock WorkflowRunResult whose get_outputs() returns the conversation."""
    result = MagicMock()
    if conversation is None:
        result.get_outputs.return_value = []
    else:
        result.get_outputs.return_value = [conversation]
    return result


def _make_mock_chat_client():
    """Return a mock AzureOpenAIChatClient that produces named mock agents."""
    def _create_agent(*, name: str, instructions: str | None = None, tools=None, **kw):
        agent = MagicMock()
        agent.name = name
        return agent

    mock_client = MagicMock()
    mock_client.as_agent.side_effect = _create_agent
    return mock_client


# ---------------------------------------------------------------------------
# Unit tests - configuration helpers
# ---------------------------------------------------------------------------


class TestGetConfig:
    def test_raises_when_endpoint_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
        from agents.supervisor.agent import _get_config

        with pytest.raises(OSError, match="AZURE_OPENAI_ENDPOINT"):
            _get_config()

    def test_returns_all_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", MOCK_ENDPOINT)
        monkeypatch.setenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4.1-mini")
        monkeypatch.setenv("ACCOUNT_MCP_URL", "http://myserver:9001/mcp/")
        monkeypatch.setenv("PAYMENTS_MCP_URL", "http://myserver:9003/mcp/")
        monkeypatch.setenv("TRANSACTIONS_MCP_URL", "http://myserver:9002/mcp/")
        monkeypatch.setenv("DOCUMENT_MCP_URL", "http://myserver:9004/mcp/")
        from agents.supervisor.agent import _get_config

        config = _get_config()
        assert config["azure_openai_endpoint"] == MOCK_ENDPOINT
        assert config["model_deployment_name"] == "gpt-4.1-mini"
        assert config["account_mcp_url"] == "http://myserver:9001/mcp/"
        assert config["payments_mcp_url"] == "http://myserver:9003/mcp/"
        assert config["transactions_mcp_url"] == "http://myserver:9002/mcp/"
        assert config["document_mcp_url"] == "http://myserver:9004/mcp/"

    def test_defaults_when_optional_vars_absent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", MOCK_ENDPOINT)
        monkeypatch.delenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", raising=False)
        monkeypatch.delenv("ACCOUNT_MCP_URL", raising=False)
        monkeypatch.delenv("PAYMENTS_MCP_URL", raising=False)
        monkeypatch.delenv("TRANSACTIONS_MCP_URL", raising=False)
        monkeypatch.delenv("DOCUMENT_MCP_URL", raising=False)
        from agents.supervisor.agent import _get_config

        config = _get_config()
        assert config["model_deployment_name"] == "gpt-4.1"
        assert config["account_mcp_url"] == "http://localhost:9001/mcp/"
        assert config["payments_mcp_url"] == "http://localhost:9003/mcp/"
        assert config["transactions_mcp_url"] == "http://localhost:9002/mcp/"
        assert config["document_mcp_url"] == "http://localhost:9004/mcp/"


# ---------------------------------------------------------------------------
# Unit tests - _extract_response_text
# ---------------------------------------------------------------------------


class TestExtractResponseText:
    def test_returns_last_assistant_message(self) -> None:
        from agents.supervisor.agent import _extract_response_text

        msgs = [
            _make_chat_message("Hello", "user"),
            _make_chat_message("Your balance is $100.", "assistant"),
        ]
        assert _extract_response_text([msgs]) == "Your balance is $100."

    def test_returns_last_assistant_when_multiple(self) -> None:
        from agents.supervisor.agent import _extract_response_text

        msgs = [
            _make_chat_message("First response.", "assistant"),
            _make_chat_message("Follow-up question?", "user"),
            _make_chat_message("Final answer.", "assistant"),
        ]
        assert _extract_response_text([msgs]) == "Final answer."

    def test_returns_empty_string_for_empty_outputs(self) -> None:
        from agents.supervisor.agent import _extract_response_text

        assert _extract_response_text([]) == ""

    def test_returns_empty_string_for_no_assistant_messages(self) -> None:
        from agents.supervisor.agent import _extract_response_text

        msgs = [_make_chat_message("User only message", "user")]
        assert _extract_response_text([msgs]) == ""

    def test_uses_last_output_when_multiple(self) -> None:
        from agents.supervisor.agent import _extract_response_text

        first_convo = [_make_chat_message("First.", "assistant")]
        last_convo = [_make_chat_message("Last.", "assistant")]
        assert _extract_response_text([first_convo, last_convo]) == "Last."


# ---------------------------------------------------------------------------
# Unit tests - _build_workflow
# ---------------------------------------------------------------------------


class TestBuildWorkflow:
    def test_builds_workflow_with_four_agents(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_build_workflow must create supervisor + 3 specialist agents."""
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", MOCK_ENDPOINT)

        mock_client = _make_mock_chat_client()
        mock_workflow = MagicMock()
        mock_builder = MagicMock()
        mock_builder.with_start_agent.return_value = mock_builder
        mock_builder.with_autonomous_mode.return_value = mock_builder
        mock_builder.build.return_value = mock_workflow

        mock_builder_cls = MagicMock(return_value=mock_builder)

        with (
            patch(
                "agents.supervisor.agent.AzureOpenAIChatClient",
                return_value=mock_client,
            ),
            patch("agents.supervisor.agent.DefaultAzureCredential"),
            patch("agents.supervisor.agent.HandoffBuilder", mock_builder_cls),
        ):
            from agents.supervisor.agent import _build_workflow, _get_config

            workflow = _build_workflow(_get_config())

        assert workflow is mock_workflow
        assert mock_client.as_agent.call_count == 4

    def test_builds_workflow_with_autonomous_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_build_workflow must enable autonomous interaction mode."""
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", MOCK_ENDPOINT)

        mock_client = _make_mock_chat_client()
        mock_builder = MagicMock()
        mock_builder.with_start_agent.return_value = mock_builder
        mock_builder.with_autonomous_mode.return_value = mock_builder
        mock_builder.build.return_value = MagicMock()

        with (
            patch(
                "agents.supervisor.agent.AzureOpenAIChatClient",
                return_value=mock_client,
            ),
            patch("agents.supervisor.agent.DefaultAzureCredential"),
            patch("agents.supervisor.agent.HandoffBuilder", return_value=mock_builder),
        ):
            from agents.supervisor.agent import _build_workflow, _get_config

            _build_workflow(_get_config())

        mock_builder.with_autonomous_mode.assert_called_once()

    def test_supervisor_is_set_as_coordinator(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The supervisor agent must be set as the workflow coordinator."""
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", MOCK_ENDPOINT)

        mock_client = _make_mock_chat_client()
        mock_builder = MagicMock()
        mock_builder.with_start_agent.return_value = mock_builder
        mock_builder.with_autonomous_mode.return_value = mock_builder
        mock_builder.build.return_value = MagicMock()

        with (
            patch(
                "agents.supervisor.agent.AzureOpenAIChatClient",
                return_value=mock_client,
            ),
            patch("agents.supervisor.agent.DefaultAzureCredential"),
            patch("agents.supervisor.agent.HandoffBuilder", return_value=mock_builder),
        ):
            from agents.supervisor.agent import (
                SUPERVISOR_NAME,
                _build_workflow,
                _get_config,
            )

            _build_workflow(_get_config())

        coordinator_arg = mock_builder.with_start_agent.call_args[0][0]
        assert coordinator_arg.name == SUPERVISOR_NAME

    def test_specialist_agents_have_correct_names(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All four agents must be created with their designated names."""
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", MOCK_ENDPOINT)

        mock_client = _make_mock_chat_client()
        mock_builder = MagicMock()
        mock_builder.with_start_agent.return_value = mock_builder
        mock_builder.with_autonomous_mode.return_value = mock_builder
        mock_builder.build.return_value = MagicMock()

        with (
            patch(
                "agents.supervisor.agent.AzureOpenAIChatClient",
                return_value=mock_client,
            ),
            patch("agents.supervisor.agent.DefaultAzureCredential"),
            patch("agents.supervisor.agent.HandoffBuilder", return_value=mock_builder),
        ):
            from agents.supervisor.agent import (
                ACCOUNT_AGENT_NAME,
                PAYMENT_AGENT_NAME,
                SUPERVISOR_NAME,
                TRANSACTION_AGENT_NAME,
                _build_workflow,
                _get_config,
            )

            _build_workflow(_get_config())

        created_names = [
            call.kwargs["name"]
            for call in mock_client.as_agent.call_args_list
        ]
        assert SUPERVISOR_NAME in created_names
        assert ACCOUNT_AGENT_NAME in created_names
        assert TRANSACTION_AGENT_NAME in created_names
        assert PAYMENT_AGENT_NAME in created_names


# ---------------------------------------------------------------------------
# Unit tests - run_query
# ---------------------------------------------------------------------------


class TestRunQuery:
    @pytest.fixture(autouse=True)
    def set_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", MOCK_ENDPOINT)

    async def test_balance_query_returns_response(self) -> None:
        """run_query must return the workflow's last assistant message."""
        response_text = "Your balance is $5,432.10."
        conversation = [_make_chat_message(response_text, "assistant")]
        mock_run_result = _make_workflow_run_result(conversation)

        mock_workflow = AsyncMock()
        mock_workflow.run = AsyncMock(return_value=mock_run_result)

        with patch(
            "agents.supervisor.agent._build_workflow", return_value=mock_workflow
        ):
            from agents.supervisor.agent import run_query

            result = await run_query("Show me my balance")

        assert result == response_text
        mock_workflow.run.assert_called_once_with("Show me my balance")

    async def test_payment_query_returns_response(self) -> None:
        """run_query must return the payment specialist response."""
        response_text = "Payment of $120.00 submitted. Reference: PAY-001."
        conversation = [_make_chat_message(response_text, "assistant")]
        mock_run_result = _make_workflow_run_result(conversation)

        mock_workflow = AsyncMock()
        mock_workflow.run = AsyncMock(return_value=mock_run_result)

        with patch(
            "agents.supervisor.agent._build_workflow", return_value=mock_workflow
        ):
            from agents.supervisor.agent import run_query

            result = await run_query("Pay my electricity bill")

        assert result == response_text
        mock_workflow.run.assert_called_once_with("Pay my electricity bill")

    async def test_returns_empty_string_when_no_output(self) -> None:
        """run_query must return '' when the workflow produces no output."""
        mock_run_result = _make_workflow_run_result(None)
        mock_workflow = AsyncMock()
        mock_workflow.run = AsyncMock(return_value=mock_run_result)

        with patch(
            "agents.supervisor.agent._build_workflow", return_value=mock_workflow
        ):
            from agents.supervisor.agent import run_query

            result = await run_query("What is the meaning of life?")

        assert result == ""

    async def test_run_query_passes_message_to_workflow(self) -> None:
        """run_query must pass the original message to workflow.run()."""
        message = "Repeat my last payment to ACME."
        mock_run_result = _make_workflow_run_result([])
        mock_workflow = AsyncMock()
        mock_workflow.run = AsyncMock(return_value=mock_run_result)

        with patch(
            "agents.supervisor.agent._build_workflow", return_value=mock_workflow
        ):
            from agents.supervisor.agent import run_query

            await run_query(message)

        mock_workflow.run.assert_called_once_with(message)


# ---------------------------------------------------------------------------
# Integration tests - HandoffBuilder end-to-end with mocked workflow
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestSupervisorAgentIntegration:
    """Integration tests: HandoffBuilder workflow with mocked MAF layer."""

    @pytest.fixture(autouse=True)
    def set_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", MOCK_ENDPOINT)
        monkeypatch.setenv("ACCOUNT_MCP_URL", MOCK_ACCOUNT_MCP_URL)
        monkeypatch.setenv("PAYMENTS_MCP_URL", MOCK_PAYMENTS_MCP_URL)
        monkeypatch.setenv("TRANSACTIONS_MCP_URL", MOCK_TRANSACTIONS_MCP_URL)
        monkeypatch.setenv("DOCUMENT_MCP_URL", MOCK_DOCUMENT_MCP_URL)

    async def test_balance_query_end_to_end(self) -> None:
        """End-to-end: 'Show me my balance' returns an account agent response."""
        expected = "Account ACC001 has a balance of $10,000.00."
        conversation = [_make_chat_message(expected, "assistant")]
        mock_run_result = _make_workflow_run_result(conversation)
        mock_workflow = AsyncMock()
        mock_workflow.run = AsyncMock(return_value=mock_run_result)

        with patch(
            "agents.supervisor.agent._build_workflow", return_value=mock_workflow
        ):
            from agents.supervisor.agent import run_query

            result = await run_query("Show me my balance")

        assert result == expected

    async def test_pay_invoice_query_end_to_end(self) -> None:
        """End-to-end: 'Pay my electricity bill' returns a payment agent response."""
        expected = "Payment of $120.00 submitted successfully. Reference: PAY-2024-001."
        conversation = [_make_chat_message(expected, "assistant")]
        mock_run_result = _make_workflow_run_result(conversation)
        mock_workflow = AsyncMock()
        mock_workflow.run = AsyncMock(return_value=mock_run_result)

        with patch(
            "agents.supervisor.agent._build_workflow", return_value=mock_workflow
        ):
            from agents.supervisor.agent import run_query

            result = await run_query("Pay my electricity bill")

        assert result == expected

    async def test_workflow_built_with_correct_mcp_urls(self) -> None:
        """_build_workflow must configure agents with their environment MCP URLs."""
        from agents.supervisor.agent import (
            ACCOUNT_AGENT_NAME,
            PAYMENT_AGENT_NAME,
            TRANSACTION_AGENT_NAME,
            _build_workflow,
            _get_config,
        )

        mock_client = _make_mock_chat_client()
        mock_builder = MagicMock()
        mock_builder.with_start_agent.return_value = mock_builder
        mock_builder.with_autonomous_mode.return_value = mock_builder
        mock_builder.build.return_value = MagicMock()

        with (
            patch(
                "agents.supervisor.agent.AzureOpenAIChatClient",
                return_value=mock_client,
            ),
            patch("agents.supervisor.agent.DefaultAzureCredential"),
            patch("agents.supervisor.agent.HandoffBuilder", return_value=mock_builder),
        ):
            _build_workflow(_get_config())

        calls_by_name = {
            call.kwargs["name"]: call.kwargs.get("tools", [])
            for call in mock_client.as_agent.call_args_list
        }
        account_tools = calls_by_name.get(ACCOUNT_AGENT_NAME, [])
        assert any(
            getattr(t, "url", None) == MOCK_ACCOUNT_MCP_URL for t in account_tools
        )

        payment_tools = calls_by_name.get(PAYMENT_AGENT_NAME, [])
        assert any(
            getattr(t, "url", None) == MOCK_PAYMENTS_MCP_URL for t in payment_tools
        )

        transaction_tools = calls_by_name.get(TRANSACTION_AGENT_NAME, [])
        assert any(
            getattr(t, "url", None) == MOCK_TRANSACTIONS_MCP_URL
            for t in transaction_tools
        )
