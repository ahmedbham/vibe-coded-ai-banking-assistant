"""Account Agent for the banking assistant.

Uses Microsoft Agent Framework (MAF) with:
- GPT-4.1 via Azure OpenAI (DefaultAzureCredential)
- Account MCP server for account / balance / payment data via streamable-HTTP MCP
"""

from __future__ import annotations

import os


# ---------------------------------------------------------------------------
# Compatibility shim – azure-ai-projects 2.0.0b4 renamed several classes that
# agent-framework-azure-ai==1.0.0b260107 still imports under the old names.
# Apply the aliases BEFORE importing any agent_framework module so the
# top-level package __init__ (which re-exports AzureAIClient) succeeds.
# ---------------------------------------------------------------------------
def _patch_azure_ai_projects() -> None:
    """Add renamed class aliases for azure-ai-projects 2.0.0b4 compatibility."""
    try:
        import azure.ai.projects.models as _m  # noqa: PLC0415

        _aliases: dict[str, str] = {
            "PromptAgentDefinitionText": "PromptAgentDefinitionTextOptions",
            "ResponseTextFormatConfigurationJsonObject": (
                "TextResponseFormatConfigurationResponseFormatJsonObject"
            ),
            "ResponseTextFormatConfigurationText": (
                "TextResponseFormatConfigurationResponseFormatText"
            ),
            "ResponseTextFormatConfigurationJsonSchema": "TextResponseFormatJsonSchema",
        }
        for alias, real_name in _aliases.items():
            if not hasattr(_m, alias) and hasattr(_m, real_name):
                setattr(_m, alias, getattr(_m, real_name))
    except (ImportError, AttributeError):
        pass


_patch_azure_ai_projects()

from azure.identity import DefaultAzureCredential, get_bearer_token_provider  # noqa: E402
from openai import AsyncAzureOpenAI  # noqa: E402

from agent_framework import ChatAgent, MCPStreamableHTTPTool  # noqa: E402
from agent_framework.openai import OpenAIChatClient  # noqa: E402

# ---------------------------------------------------------------------------
# Environment configuration
# ---------------------------------------------------------------------------
ACCOUNT_MCP_URL: str = os.getenv("ACCOUNT_MCP_URL", "http://localhost:9001")
AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_VERSION: str = os.getenv(
    "AZURE_OPENAI_API_VERSION", "2024-12-01-preview"
)
MODEL_DEPLOYMENT_NAME: str = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4.1")

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT: str = """\
You are a secure banking account assistant. You help customers with:
- Account information and profile details
- Credit and debit balance inquiries
- Payment methods registered on the account
- Registered beneficiaries and transfer recipients

You have access to tools that can retrieve real account data. Always use these tools
to provide accurate, up-to-date information. Be concise, professional, and
security-conscious in your responses. Do not reveal sensitive information beyond
what is strictly needed to answer the customer's query.
"""


# ---------------------------------------------------------------------------
# AccountAgent
# ---------------------------------------------------------------------------
class AccountAgent:
    """Banking account agent powered by Microsoft Agent Framework.

    The agent is lazily initialised: the internal :class:`ChatAgent` (and its
    Azure OpenAI client) are only created on the first :meth:`chat` call.
    For testing, a pre-built ``chat_agent`` can be injected directly.

    Parameters
    ----------
    chat_agent:
        Optional pre-built :class:`~agent_framework.ChatAgent`.  When supplied
        the agent is used as-is and no Azure credentials are required.
    mcp_url:
        Base URL for the account MCP server.  Defaults to the
        ``ACCOUNT_MCP_URL`` environment variable (``http://localhost:9001``).
    """

    def __init__(
        self,
        *,
        chat_agent: ChatAgent | None = None,
        mcp_url: str | None = None,
    ) -> None:
        self._mcp_url: str = mcp_url or ACCOUNT_MCP_URL
        self._chat_agent: ChatAgent | None = chat_agent

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_chat_agent(self) -> ChatAgent:
        """Construct a :class:`ChatAgent` backed by Azure OpenAI + MCP."""
        credential = DefaultAzureCredential()
        token_provider = get_bearer_token_provider(
            credential, "https://cognitiveservices.azure.com/.default"
        )
        aoai_client = AsyncAzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            azure_ad_token_provider=token_provider,
            api_version=AZURE_OPENAI_API_VERSION,
        )
        chat_client = OpenAIChatClient(
            model_id=MODEL_DEPLOYMENT_NAME,
            async_client=aoai_client,
        )
        mcp_tool = MCPStreamableHTTPTool(
            name="account_mcp",
            # FastMCP http_app() (default "http" transport) serves at /mcp
            url=f"{self._mcp_url}/mcp",
        )
        return ChatAgent(
            chat_client=chat_client,
            instructions=SYSTEM_PROMPT,
            tools=[mcp_tool],
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def agent(self) -> ChatAgent:
        """Return the underlying :class:`ChatAgent`, building it on first access."""
        if self._chat_agent is None:
            self._chat_agent = self._build_chat_agent()
        return self._chat_agent

    async def chat(self, message: str) -> str:
        """Process a user message and return the agent's response.

        Parameters
        ----------
        message:
            The customer's natural-language query.

        Returns
        -------
        str
            The agent's text response (empty string if the model produced no
            text content).
        """
        thread = self.agent.get_new_thread()
        response = await self.agent.run(message, thread=thread)
        return response.text or ""
