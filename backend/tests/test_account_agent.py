"""Tests for the Account Agent.

Structure
---------
Unit tests (``TestAccountAgentInit``, ``TestAccountAgentChat``)
    Mock the entire MAF SDK – no real Azure calls, no network I/O.

Integration tests (``TestAccountAgentMcpIntegration``)
    Start the account MCP server on a real loopback port via uvicorn so that
    ``MCPStreamableHTTPTool`` can connect over HTTP.  Azure OpenAI is mocked
    at the ``openai.AsyncAzureOpenAI`` level; the MCP transport is real.
"""

from __future__ import annotations

import asyncio
import socket
import threading
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import uvicorn

import mcp.account_mcp as account_mcp_module
from mcp.account_mcp import mcp as account_mcp_server
from services.account_service import app as account_app

# ---------------------------------------------------------------------------
# Import the agent module (the compatibility patch runs at module import time)
# ---------------------------------------------------------------------------
from agents.account.agent import (
    ACCOUNT_MCP_URL,
    MODEL_DEPLOYMENT_NAME,
    SYSTEM_PROMPT,
    AccountAgent,
)
from agent_framework import ChatAgent, MCPStreamableHTTPTool
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


# ===========================================================================
# Helpers / shared fixtures
# ===========================================================================


def _free_port() -> int:
    """Return an unused TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ===========================================================================
# Unit tests – AccountAgent initialisation
# ===========================================================================


class TestAccountAgentInit:
    """Verify constructor behaviour without touching Azure or the network."""

    def test_default_mcp_url(self) -> None:
        agent = AccountAgent()
        assert agent._mcp_url == "http://localhost:9001"

    def test_env_var_mcp_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ACCOUNT_MCP_URL", "http://custom-host:8888")
        # Re-import to pick up the env var at module level
        import importlib
        import agents.account.agent as agent_mod

        importlib.reload(agent_mod)
        agent = agent_mod.AccountAgent()
        assert agent._mcp_url == "http://custom-host:8888"
        # Restore
        importlib.reload(agent_mod)

    def test_custom_mcp_url_kwarg(self) -> None:
        agent = AccountAgent(mcp_url="http://example.com:9999")
        assert agent._mcp_url == "http://example.com:9999"

    def test_injected_chat_agent_is_used_directly(self) -> None:
        mock_agent = MagicMock(spec=ChatAgent)
        account_agent = AccountAgent(chat_agent=mock_agent)
        # .agent property must return the injected instance
        assert account_agent.agent is mock_agent

    def test_no_agent_built_before_access(self) -> None:
        account_agent = AccountAgent()
        assert account_agent._chat_agent is None

    def test_system_prompt_covers_required_topics(self) -> None:
        lower = SYSTEM_PROMPT.lower()
        assert "account" in lower, "SYSTEM_PROMPT should mention 'account'"
        assert "balance" in lower, "SYSTEM_PROMPT should mention 'balance'"
        assert "payment" in lower, "SYSTEM_PROMPT should mention 'payment'"

    def test_default_model_deployment_name(self) -> None:
        assert MODEL_DEPLOYMENT_NAME == "gpt-4.1"

    def test_default_account_mcp_url(self) -> None:
        assert ACCOUNT_MCP_URL == "http://localhost:9001"


# ===========================================================================
# Unit tests – AccountAgent.chat (fully mocked)
# ===========================================================================


class TestAccountAgentChat:
    """Verify chat() delegates to ChatAgent.run() and returns text."""

    async def test_chat_returns_text_response(self) -> None:
        mock_response = MagicMock()
        mock_response.text = "Your balance is $2,500.00."

        mock_thread = MagicMock()
        mock_agent = MagicMock(spec=ChatAgent)
        mock_agent.get_new_thread.return_value = mock_thread
        mock_agent.run = AsyncMock(return_value=mock_response)

        account_agent = AccountAgent(chat_agent=mock_agent)
        result = await account_agent.chat("What is my balance?")

        assert result == "Your balance is $2,500.00."
        mock_agent.run.assert_awaited_once_with(
            "What is my balance?", thread=mock_thread
        )

    async def test_chat_passes_message_to_run(self) -> None:
        mock_response = MagicMock()
        mock_response.text = "ACC001"

        mock_agent = MagicMock(spec=ChatAgent)
        mock_agent.get_new_thread.return_value = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_response)

        await AccountAgent(chat_agent=mock_agent).chat("Show my account ID")
        mock_agent.run.assert_awaited_once()
        call_args = mock_agent.run.call_args
        assert call_args.args[0] == "Show my account ID"

    async def test_chat_returns_empty_string_when_text_is_none(self) -> None:
        mock_response = MagicMock()
        mock_response.text = None

        mock_agent = MagicMock(spec=ChatAgent)
        mock_agent.get_new_thread.return_value = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_response)

        result = await AccountAgent(chat_agent=mock_agent).chat("anything")
        assert result == ""

    async def test_chat_creates_new_thread_per_call(self) -> None:
        mock_response = MagicMock()
        mock_response.text = "ok"

        thread_a, thread_b = MagicMock(), MagicMock()
        mock_agent = MagicMock(spec=ChatAgent)
        mock_agent.get_new_thread.side_effect = [thread_a, thread_b]
        mock_agent.run = AsyncMock(return_value=mock_response)

        agent = AccountAgent(chat_agent=mock_agent)
        await agent.chat("first")
        await agent.chat("second")

        assert mock_agent.get_new_thread.call_count == 2
        calls = mock_agent.run.await_args_list
        assert calls[0].kwargs["thread"] is thread_a
        assert calls[1].kwargs["thread"] is thread_b

    def test_build_chat_agent_uses_correct_mcp_url(self) -> None:
        """_build_chat_agent should embed the /mcp path suffix."""
        agent = AccountAgent(mcp_url="http://mcp-host:1234")

        with (
            patch("agents.account.agent.DefaultAzureCredential"),
            patch("agents.account.agent.get_bearer_token_provider"),
            patch("agents.account.agent.AsyncAzureOpenAI"),
            patch("agents.account.agent.OpenAIChatClient"),
            patch("agents.account.agent.MCPStreamableHTTPTool") as mock_mcp_cls,
            patch("agents.account.agent.ChatAgent"),
        ):
            agent._build_chat_agent()

        mock_mcp_cls.assert_called_once()
        _, kwargs = mock_mcp_cls.call_args
        assert kwargs.get("url") == "http://mcp-host:1234/mcp"

    def test_build_chat_agent_uses_system_prompt(self) -> None:
        """_build_chat_agent should pass SYSTEM_PROMPT as instructions."""
        agent = AccountAgent(mcp_url="http://mcp-host:1234")

        with (
            patch("agents.account.agent.DefaultAzureCredential"),
            patch("agents.account.agent.get_bearer_token_provider"),
            patch("agents.account.agent.AsyncAzureOpenAI"),
            patch("agents.account.agent.OpenAIChatClient"),
            patch("agents.account.agent.MCPStreamableHTTPTool"),
            patch("agents.account.agent.ChatAgent") as mock_chat_agent_cls,
        ):
            agent._build_chat_agent()

        _, kwargs = mock_chat_agent_cls.call_args
        assert kwargs.get("instructions") == SYSTEM_PROMPT

    def test_build_chat_agent_uses_default_azure_credential(self) -> None:
        """_build_chat_agent should authenticate via DefaultAzureCredential."""
        agent = AccountAgent(mcp_url="http://mcp-host:1234")

        with (
            patch("agents.account.agent.DefaultAzureCredential") as mock_cred_cls,
            patch("agents.account.agent.get_bearer_token_provider"),
            patch("agents.account.agent.AsyncAzureOpenAI"),
            patch("agents.account.agent.OpenAIChatClient"),
            patch("agents.account.agent.MCPStreamableHTTPTool"),
            patch("agents.account.agent.ChatAgent"),
        ):
            agent._build_chat_agent()

        mock_cred_cls.assert_called_once()


# ===========================================================================
# Integration tests – real MCP server over loopback HTTP
# ===========================================================================


@pytest.fixture(scope="class")
def account_mcp_base_url(monkeypatch_class: Any) -> str:
    """Start the account MCP server on a free port and return its base URL.

    Patches ``account_mcp._get_client`` so the MCP tools hit the in-process
    mock account service (no external HTTP calls).
    """
    from httpx import ASGITransport, AsyncClient

    def _mock_client() -> AsyncClient:
        return AsyncClient(
            transport=ASGITransport(app=account_app), base_url="http://test"
        )

    monkeypatch_class.setattr(account_mcp_module, "_get_client", _mock_client)

    port = _free_port()
    http_app = account_mcp_server.http_app()
    config = uvicorn.Config(
        http_app, host="127.0.0.1", port=port, log_level="error"
    )
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()

    # Wait until the server is accepting connections (up to 5 s)
    import time

    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                break
        except OSError:
            time.sleep(0.05)

    yield f"http://127.0.0.1:{port}"  # type: ignore[misc]

    server.should_exit = True
    t.join(timeout=2)


# Provide a class-scoped monkeypatch fixture (pytest only supplies it function-scoped)
@pytest.fixture(scope="class")
def monkeypatch_class() -> Any:
    from _pytest.monkeypatch import MonkeyPatch

    mp = MonkeyPatch()
    yield mp
    mp.undo()


class TestAccountAgentMcpIntegration:
    """Integration tests: real MCP server + mocked Azure OpenAI."""

    async def test_mcp_tool_lists_account_tools(
        self, account_mcp_base_url: str
    ) -> None:
        """MCPStreamableHTTPTool should discover the account tools."""
        mcp_tool = MCPStreamableHTTPTool(
            name="account_mcp",
            url=f"{account_mcp_base_url}/mcp",
        )
        async with mcp_tool.get_mcp_client() as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()

        tool_names = {t.name for t in tools.tools}
        assert "getAccountByUsername" in tool_names
        assert "getAccountDetails" in tool_names
        assert "getPaymentMethods" in tool_names
        assert "getRegisteredBeneficiaries" in tool_names

    async def test_mcp_tool_get_account_by_username(
        self, account_mcp_base_url: str
    ) -> None:
        """MCPStreamableHTTPTool should be able to call getAccountByUsername."""
        mcp_tool = MCPStreamableHTTPTool(
            name="account_mcp",
            url=f"{account_mcp_base_url}/mcp",
        )
        async with mcp_tool.get_mcp_client() as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "getAccountByUsername", {"username": "john_doe"}
                )

        assert result.content, "Expected non-empty tool result"
        # FastMCP returns tool results as text; parse the dict representation
        content_text = result.content[0].text  # type: ignore[union-attr]
        assert "john_doe" in content_text
        assert "ACC001" in content_text

    async def test_mcp_tool_get_account_details(
        self, account_mcp_base_url: str
    ) -> None:
        """MCPStreamableHTTPTool should be able to call getAccountDetails."""
        mcp_tool = MCPStreamableHTTPTool(
            name="account_mcp",
            url=f"{account_mcp_base_url}/mcp",
        )
        async with mcp_tool.get_mcp_client() as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "getAccountDetails", {"account_id": "ACC001"}
                )

        content_text = result.content[0].text  # type: ignore[union-attr]
        assert "2500" in content_text  # balance
        assert "checking" in content_text  # account_type

    async def test_agent_chat_with_mocked_llm(
        self, account_mcp_base_url: str
    ) -> None:
        """End-to-end: agent.chat() with a mocked OpenAI response.

        The MCP transport is real (loopback HTTP); only the LLM is mocked so
        the test is deterministic and needs no Azure credentials.
        """
        from openai.types.chat import ChatCompletion, ChatCompletionMessage
        from openai.types.chat.chat_completion import Choice
        from openai.types import CompletionUsage
        from agent_framework.openai import OpenAIChatClient

        # Build a minimal mock ChatCompletion that returns a plain text answer
        mock_completion = ChatCompletion(
            id="chatcmpl-test",
            object="chat.completion",
            created=1234567890,
            model="gpt-4.1",
            choices=[
                Choice(
                    index=0,
                    message=ChatCompletionMessage(
                        role="assistant",
                        content="Your account balance is $2,500.00.",
                    ),
                    finish_reason="stop",
                )
            ],
            usage=CompletionUsage(
                prompt_tokens=10, completion_tokens=10, total_tokens=20
            ),
        )

        mock_create = AsyncMock(return_value=mock_completion)
        mock_aclient = MagicMock()
        mock_aclient.chat = MagicMock()
        mock_aclient.chat.completions = MagicMock()
        mock_aclient.chat.completions.create = mock_create

        chat_client = OpenAIChatClient(
            model_id="gpt-4.1",
            async_client=mock_aclient,
        )

        mcp_tool = MCPStreamableHTTPTool(
            name="account_mcp",
            url=f"{account_mcp_base_url}/mcp",
        )

        chat_agent = ChatAgent(
            chat_client=chat_client,
            instructions=SYSTEM_PROMPT,
            tools=[mcp_tool],
        )

        account_agent = AccountAgent(chat_agent=chat_agent)
        response = await account_agent.chat("What is my balance?")

        assert isinstance(response, str)
        assert len(response) > 0
        assert mock_create.called, "OpenAI create should have been invoked"
