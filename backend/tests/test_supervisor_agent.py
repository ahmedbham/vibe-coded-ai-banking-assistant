"""Tests for the Supervisor Agent (MAF).

Unit tests
----------
- `_get_config` raises when FOUNDRY_PROJECT_ENDPOINT is missing.
- `_get_config` picks up all environment variables.
- `_get_config` uses defaults when optional vars are absent.
- `_classify_intent` returns the correct label for all known intents.
- `_classify_intent` returns INTENT_UNKNOWN for unrecognised text.
- `create_supervisor_agent` creates the classifier with the system prompt.
- `run_query` routes "Show me my balance" to the Account Agent.
- `run_query` routes "Pay my electricity bill" to the Payment Agent.
- `run_query` routes "Repeat my last payment" to the Payment Agent.
- `run_query` routes "Show my transactions" to the Transaction Agent.

Integration tests
-----------------
Marked with `@pytest.mark.integration`.  These tests exercise the full
routing pipeline with a mocked MAF layer (no live Azure credentials needed).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MOCK_ENDPOINT = "https://mock-project.api.azureml.ms"
MOCK_MODEL = "gpt-4.1"


def _make_mock_agent(response_text: str) -> AsyncMock:
    """Return an async mock that behaves like a MAF ChatAgent."""
    mock_result = MagicMock()
    mock_result.text = response_text

    mock_agent = AsyncMock()
    mock_agent.run = AsyncMock(return_value=mock_result)
    return mock_agent


def _make_mock_specialist_factory(response_text: str):
    """Return a (mock_agent, mock_factory) pair for a specialist agent.

    The factory is callable and returns an async context manager that yields
    the mock agent.
    """
    mock_agent = _make_mock_agent(response_text)

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_agent)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    mock_factory = MagicMock(return_value=mock_cm)
    return mock_agent, mock_factory


def _patch_maf(classifier_response: str = "Unknown"):
    """Return mocks that replace the MAF layer for the supervisor's classifier.

    Returns
    -------
    tuple
        (mock_classifier_agent, mock_credential_cls, mock_client_cls)
    """
    mock_classifier = _make_mock_agent(classifier_response)

    # Mock DefaultAzureCredential (azure.identity.aio) as async CM
    mock_credential = AsyncMock()
    mock_credential.__aenter__ = AsyncMock(return_value=mock_credential)
    mock_credential.__aexit__ = AsyncMock(return_value=False)

    # Mock AzureAIClient.create_agent as async CM yielding mock_classifier
    mock_create_agent_cm = MagicMock()
    mock_create_agent_cm.__aenter__ = AsyncMock(return_value=mock_classifier)
    mock_create_agent_cm.__aexit__ = AsyncMock(return_value=False)

    mock_azure_client = MagicMock()
    mock_azure_client.create_agent = MagicMock(return_value=mock_create_agent_cm)

    mock_client_cls = MagicMock(return_value=mock_azure_client)
    mock_credential_cls = MagicMock(return_value=mock_credential)

    return mock_classifier, mock_credential_cls, mock_client_cls


# ---------------------------------------------------------------------------
# Unit tests – configuration helpers
# ---------------------------------------------------------------------------


class TestGetConfig:
    def test_raises_when_endpoint_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("FOUNDRY_PROJECT_ENDPOINT", raising=False)
        from agents.supervisor.agent import _get_config

        with pytest.raises(EnvironmentError, match="FOUNDRY_PROJECT_ENDPOINT"):
            _get_config()

    def test_returns_all_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", MOCK_ENDPOINT)
        monkeypatch.setenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4.1-mini")
        from agents.supervisor.agent import _get_config

        config = _get_config()
        assert config["project_endpoint"] == MOCK_ENDPOINT
        assert config["model_deployment_name"] == "gpt-4.1-mini"

    def test_defaults_when_optional_vars_absent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", MOCK_ENDPOINT)
        monkeypatch.delenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", raising=False)
        from agents.supervisor.agent import _get_config

        config = _get_config()
        assert config["model_deployment_name"] == "gpt-4.1"


# ---------------------------------------------------------------------------
# Unit tests – intent classification helper
# ---------------------------------------------------------------------------


class TestClassifyIntent:
    def test_account_info(self) -> None:
        from agents.supervisor.agent import INTENT_ACCOUNT, _classify_intent

        assert _classify_intent("AccountInfo") == INTENT_ACCOUNT

    def test_transactions(self) -> None:
        from agents.supervisor.agent import INTENT_TRANSACTIONS, _classify_intent

        assert _classify_intent("Transactions") == INTENT_TRANSACTIONS

    def test_pay_invoice(self) -> None:
        from agents.supervisor.agent import INTENT_PAY_INVOICE, _classify_intent

        assert _classify_intent("PayInvoice") == INTENT_PAY_INVOICE

    def test_repeat_payment(self) -> None:
        from agents.supervisor.agent import INTENT_REPEAT_PAYMENT, _classify_intent

        assert _classify_intent("RepeatPayment") == INTENT_REPEAT_PAYMENT

    def test_unknown_label(self) -> None:
        from agents.supervisor.agent import INTENT_UNKNOWN, _classify_intent

        assert _classify_intent("Unknown") == INTENT_UNKNOWN

    def test_unrecognised_text_returns_unknown(self) -> None:
        from agents.supervisor.agent import INTENT_UNKNOWN, _classify_intent

        assert _classify_intent("something random") == INTENT_UNKNOWN

    def test_empty_string_returns_unknown(self) -> None:
        from agents.supervisor.agent import INTENT_UNKNOWN, _classify_intent

        assert _classify_intent("") == INTENT_UNKNOWN

    def test_strips_whitespace(self) -> None:
        from agents.supervisor.agent import INTENT_ACCOUNT, _classify_intent

        assert _classify_intent("  AccountInfo  ") == INTENT_ACCOUNT

    def test_none_equivalent_returns_unknown(self) -> None:
        from agents.supervisor.agent import INTENT_UNKNOWN, _classify_intent

        assert _classify_intent("  ") == INTENT_UNKNOWN


# ---------------------------------------------------------------------------
# Unit tests – agent context manager wiring
# ---------------------------------------------------------------------------


class TestCreateSupervisorAgent:
    async def test_agent_created_with_system_prompt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """create_supervisor_agent must pass the system prompt to AzureAIClient."""
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", MOCK_ENDPOINT)
        monkeypatch.delenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", raising=False)

        mock_classifier, mock_credential_cls, mock_client_cls = _patch_maf()

        with (
            patch(
                "agents.supervisor.agent.DefaultAzureCredential", mock_credential_cls
            ),
            patch("agents.supervisor.agent.AzureAIClient", mock_client_cls),
        ):
            from agents.supervisor.agent import SYSTEM_PROMPT, create_supervisor_agent

            async with create_supervisor_agent() as supervisor:
                assert supervisor is not None

        mock_client_cls.assert_called_once()
        call_kwargs = mock_client_cls.call_args.kwargs
        assert call_kwargs["project_endpoint"] == MOCK_ENDPOINT

        mock_azure_client = mock_client_cls.return_value
        mock_azure_client.create_agent.assert_called_once()
        create_agent_kwargs = mock_azure_client.create_agent.call_args.kwargs
        assert create_agent_kwargs["instructions"] == SYSTEM_PROMPT
        assert create_agent_kwargs["name"] == "SupervisorAgent"
        # Supervisor classifier uses no MCP tools
        assert create_agent_kwargs["tools"] == []

    async def test_agent_created_with_custom_model_deployment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", MOCK_ENDPOINT)
        monkeypatch.setenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4.1-mini")

        _, mock_credential_cls, mock_client_cls = _patch_maf()

        with (
            patch(
                "agents.supervisor.agent.DefaultAzureCredential", mock_credential_cls
            ),
            patch("agents.supervisor.agent.AzureAIClient", mock_client_cls),
        ):
            from agents.supervisor.agent import create_supervisor_agent

            async with create_supervisor_agent():
                pass

        call_kwargs = mock_client_cls.call_args.kwargs
        assert call_kwargs["model_deployment_name"] == "gpt-4.1-mini"


# ---------------------------------------------------------------------------
# Unit tests – routing logic
# ---------------------------------------------------------------------------


class TestRouting:
    @pytest.fixture(autouse=True)
    def set_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", MOCK_ENDPOINT)

    async def test_balance_query_routes_to_account_agent(self) -> None:
        """'Show me my balance' must be routed to the Account Agent."""
        mock_classifier, mock_credential_cls, mock_client_cls = _patch_maf(
            "AccountInfo"
        )
        account_agent, mock_account_factory = _make_mock_specialist_factory(
            "Your balance is $5,432.10."
        )

        with (
            patch(
                "agents.supervisor.agent.DefaultAzureCredential", mock_credential_cls
            ),
            patch("agents.supervisor.agent.AzureAIClient", mock_client_cls),
            patch(
                "agents.supervisor.agent.create_account_agent", mock_account_factory
            ),
        ):
            from agents.supervisor.agent import run_query

            result = await run_query("Show me my balance")

        assert result == "Your balance is $5,432.10."
        mock_account_factory.assert_called_once()
        account_agent.run.assert_called_once_with("Show me my balance")

    async def test_pay_electricity_bill_routes_to_payment_agent(self) -> None:
        """'Pay my electricity bill' must be routed to the Payment Agent."""
        mock_classifier, mock_credential_cls, mock_client_cls = _patch_maf("PayInvoice")
        payment_agent, mock_payment_factory = _make_mock_specialist_factory(
            "Payment submitted successfully."
        )

        with (
            patch(
                "agents.supervisor.agent.DefaultAzureCredential", mock_credential_cls
            ),
            patch("agents.supervisor.agent.AzureAIClient", mock_client_cls),
            patch(
                "agents.supervisor.agent.create_payment_agent", mock_payment_factory
            ),
        ):
            from agents.supervisor.agent import run_query

            result = await run_query("Pay my electricity bill")

        assert result == "Payment submitted successfully."
        mock_payment_factory.assert_called_once()
        payment_agent.run.assert_called_once_with("Pay my electricity bill")

    async def test_repeat_payment_routes_to_payment_agent(self) -> None:
        """'Repeat my last payment' must be routed to the Payment Agent."""
        mock_classifier, mock_credential_cls, mock_client_cls = _patch_maf(
            "RepeatPayment"
        )
        payment_agent, mock_payment_factory = _make_mock_specialist_factory(
            "Payment resubmitted."
        )

        with (
            patch(
                "agents.supervisor.agent.DefaultAzureCredential", mock_credential_cls
            ),
            patch("agents.supervisor.agent.AzureAIClient", mock_client_cls),
            patch(
                "agents.supervisor.agent.create_payment_agent", mock_payment_factory
            ),
        ):
            from agents.supervisor.agent import run_query

            result = await run_query("Repeat my last payment to ACME")

        assert result == "Payment resubmitted."
        mock_payment_factory.assert_called_once()
        payment_agent.run.assert_called_once_with("Repeat my last payment to ACME")

    async def test_transactions_query_routes_to_transaction_agent(self) -> None:
        """'Show my transactions' must be routed to the Transaction Agent."""
        mock_classifier, mock_credential_cls, mock_client_cls = _patch_maf(
            "Transactions"
        )
        transaction_agent, mock_transaction_factory = _make_mock_specialist_factory(
            "You have 3 recent transactions."
        )

        with (
            patch(
                "agents.supervisor.agent.DefaultAzureCredential", mock_credential_cls
            ),
            patch("agents.supervisor.agent.AzureAIClient", mock_client_cls),
            patch(
                "agents.supervisor.agent.create_transaction_agent",
                mock_transaction_factory,
            ),
        ):
            from agents.supervisor.agent import run_query

            result = await run_query("Show my transactions")

        assert result == "You have 3 recent transactions."
        mock_transaction_factory.assert_called_once()
        transaction_agent.run.assert_called_once_with("Show my transactions")

    async def test_unknown_intent_returns_classifier_response(self) -> None:
        """An unrecognised intent must return the classifier's response text."""
        classifier_text = "Unknown"
        mock_classifier, mock_credential_cls, mock_client_cls = _patch_maf(
            classifier_text
        )

        with (
            patch(
                "agents.supervisor.agent.DefaultAzureCredential", mock_credential_cls
            ),
            patch("agents.supervisor.agent.AzureAIClient", mock_client_cls),
        ):
            from agents.supervisor.agent import run_query

            result = await run_query("What is the meaning of life?")

        # Result is "Unknown" from the classifier (no specialist called)
        assert result == classifier_text

    async def test_thread_forwarded_to_specialist(self) -> None:
        """The optional thread argument must be passed to the specialist agent."""
        mock_classifier, mock_credential_cls, mock_client_cls = _patch_maf(
            "AccountInfo"
        )
        account_agent, mock_account_factory = _make_mock_specialist_factory(
            "Balance details for your account."
        )
        mock_thread = MagicMock()

        with (
            patch(
                "agents.supervisor.agent.DefaultAzureCredential", mock_credential_cls
            ),
            patch("agents.supervisor.agent.AzureAIClient", mock_client_cls),
            patch(
                "agents.supervisor.agent.create_account_agent", mock_account_factory
            ),
        ):
            from agents.supervisor.agent import run_query

            await run_query("What is my credit balance?", thread=mock_thread)

        account_agent.run.assert_called_once_with(
            "What is my credit balance?", thread=mock_thread
        )

    async def test_run_query_returns_empty_string_when_no_text(self) -> None:
        """run_query must return '' when the specialist agent produces no text."""
        mock_classifier, mock_credential_cls, mock_client_cls = _patch_maf(
            "AccountInfo"
        )
        account_agent, mock_account_factory = _make_mock_specialist_factory("")
        account_agent.run.return_value.text = None

        with (
            patch(
                "agents.supervisor.agent.DefaultAzureCredential", mock_credential_cls
            ),
            patch("agents.supervisor.agent.AzureAIClient", mock_client_cls),
            patch(
                "agents.supervisor.agent.create_account_agent", mock_account_factory
            ),
        ):
            from agents.supervisor.agent import run_query

            result = await run_query("What is my balance?")

        assert result == ""

    async def test_account_agent_not_called_for_payment_intent(self) -> None:
        """Account agent factory must NOT be invoked when intent is PayInvoice."""
        mock_classifier, mock_credential_cls, mock_client_cls = _patch_maf("PayInvoice")
        _, mock_account_factory = _make_mock_specialist_factory("account response")
        _, mock_payment_factory = _make_mock_specialist_factory("Payment done.")

        with (
            patch(
                "agents.supervisor.agent.DefaultAzureCredential", mock_credential_cls
            ),
            patch("agents.supervisor.agent.AzureAIClient", mock_client_cls),
            patch(
                "agents.supervisor.agent.create_account_agent", mock_account_factory
            ),
            patch(
                "agents.supervisor.agent.create_payment_agent", mock_payment_factory
            ),
        ):
            from agents.supervisor.agent import run_query

            await run_query("Pay invoice from URL")

        mock_account_factory.assert_not_called()
        mock_payment_factory.assert_called_once()


# ---------------------------------------------------------------------------
# Integration tests – end-to-end hand-off with mock specialist agents
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestSupervisorAgentIntegration:
    """Integration tests: routing pipeline with mocked MAF and specialist agents."""

    @pytest.fixture(autouse=True)
    def set_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", MOCK_ENDPOINT)

    async def test_balance_query_end_to_end(self) -> None:
        """End-to-end: 'Show me my balance' routes to Account Agent."""
        mock_classifier, mock_credential_cls, mock_client_cls = _patch_maf(
            "AccountInfo"
        )
        account_agent, mock_account_factory = _make_mock_specialist_factory(
            "Account ACC001 has a balance of $10,000.00."
        )

        with (
            patch(
                "agents.supervisor.agent.DefaultAzureCredential", mock_credential_cls
            ),
            patch("agents.supervisor.agent.AzureAIClient", mock_client_cls),
            patch(
                "agents.supervisor.agent.create_account_agent", mock_account_factory
            ),
        ):
            from agents.supervisor.agent import run_query

            result = await run_query("Show me my balance")

        assert result == "Account ACC001 has a balance of $10,000.00."
        account_agent.run.assert_called_once_with("Show me my balance")

    async def test_payment_query_end_to_end(self) -> None:
        """End-to-end: 'Pay my electricity bill' routes to Payment Agent."""
        mock_classifier, mock_credential_cls, mock_client_cls = _patch_maf("PayInvoice")
        payment_agent, mock_payment_factory = _make_mock_specialist_factory(
            "Payment of $120.00 submitted. Reference: PAY-2024-001."
        )

        with (
            patch(
                "agents.supervisor.agent.DefaultAzureCredential", mock_credential_cls
            ),
            patch("agents.supervisor.agent.AzureAIClient", mock_client_cls),
            patch(
                "agents.supervisor.agent.create_payment_agent", mock_payment_factory
            ),
        ):
            from agents.supervisor.agent import run_query

            result = await run_query("Pay my electricity bill")

        assert result == "Payment of $120.00 submitted. Reference: PAY-2024-001."
        payment_agent.run.assert_called_once_with("Pay my electricity bill")

    async def test_create_supervisor_agent_lifecycle(self) -> None:
        """create_supervisor_agent must yield a _SupervisorAgent instance."""
        mock_classifier, mock_credential_cls, mock_client_cls = _patch_maf("Unknown")

        with (
            patch(
                "agents.supervisor.agent.DefaultAzureCredential", mock_credential_cls
            ),
            patch("agents.supervisor.agent.AzureAIClient", mock_client_cls),
        ):
            from agents.supervisor.agent import (
                _SupervisorAgent,
                create_supervisor_agent,
            )

            async with create_supervisor_agent() as supervisor:
                assert isinstance(supervisor, _SupervisorAgent)

        # Verify classifier was created with proper args
        mock_client_cls.assert_called_once()
        mock_azure_client = mock_client_cls.return_value
        mock_azure_client.create_agent.assert_called_once()
