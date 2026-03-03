"""Tests for the Chat API – POST /chat endpoint.

Unit tests
----------
- POST /chat returns 200 and streams the agent response.
- POST /chat with empty session_id still works.
- POST /chat returns 500 when FOUNDRY_PROJECT_ENDPOINT is missing.
- POST /chat returns 500 when the supervisor agent raises an unexpected error.
- POST /chat body with only ``message`` (session_id defaults to "") works.
- GET /health returns {"status": "ok"}.

All tests mock ``agents.supervisor.agent.run_query`` so that no live Azure
services are needed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def app():
    """Return the FastAPI application with a no-op tracer."""
    from api.main import app as _app

    return _app


@pytest.fixture()
async def client(app):
    """Return an httpx AsyncClient wired to the FastAPI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# POST /chat – happy-path tests
# ---------------------------------------------------------------------------


class TestChatEndpoint:
    async def test_returns_200_with_agent_response(self, client: AsyncClient) -> None:
        """POST /chat must return 200 and the supervisor's response text."""
        expected = "Your current balance is $5,432.10."

        with patch(
            "api.chat.run_query", new_callable=AsyncMock, return_value=expected
        ):
            response = await client.post(
                "/chat",
                json={"message": "What is my balance?", "session_id": "sess-001"},
            )

        assert response.status_code == 200
        assert response.text == expected

    async def test_response_content_type_is_text_plain(
        self, client: AsyncClient
    ) -> None:
        """POST /chat must return content-type text/plain."""
        with patch(
            "api.chat.run_query", new_callable=AsyncMock, return_value="OK"
        ):
            response = await client.post(
                "/chat",
                json={"message": "Hello", "session_id": "sess-002"},
            )

        assert "text/plain" in response.headers["content-type"]

    async def test_empty_session_id_is_accepted(self, client: AsyncClient) -> None:
        """POST /chat must accept an empty session_id."""
        with patch(
            "api.chat.run_query", new_callable=AsyncMock, return_value="response"
        ):
            response = await client.post(
                "/chat",
                json={"message": "Ping", "session_id": ""},
            )

        assert response.status_code == 200

    async def test_session_id_defaults_to_empty_string(
        self, client: AsyncClient
    ) -> None:
        """POST /chat must work when session_id is omitted from the body."""
        with patch(
            "api.chat.run_query", new_callable=AsyncMock, return_value="pong"
        ):
            response = await client.post(
                "/chat",
                json={"message": "Ping"},
            )

        assert response.status_code == 200
        assert response.text == "pong"

    async def test_run_query_is_called_with_message(
        self, client: AsyncClient
    ) -> None:
        """POST /chat must forward the message to run_query."""
        mock_run_query = AsyncMock(return_value="answer")

        with patch("api.chat.run_query", mock_run_query):
            await client.post(
                "/chat",
                json={"message": "Show my transactions", "session_id": "s1"},
            )

        mock_run_query.assert_called_once_with("Show my transactions")

    async def test_empty_agent_response_is_streamed(
        self, client: AsyncClient
    ) -> None:
        """POST /chat must succeed even when the agent returns an empty string."""
        with patch(
            "api.chat.run_query", new_callable=AsyncMock, return_value=""
        ):
            response = await client.post(
                "/chat",
                json={"message": "...", "session_id": "sess-003"},
            )

        assert response.status_code == 200
        assert response.text == ""


# ---------------------------------------------------------------------------
# POST /chat – error handling
# ---------------------------------------------------------------------------


class TestChatEndpointErrors:
    async def test_returns_500_on_os_error(self, client: AsyncClient) -> None:
        """POST /chat must return 500 when run_query raises OSError."""
        with patch(
            "api.chat.run_query",
            new_callable=AsyncMock,
            side_effect=OSError("FOUNDRY_PROJECT_ENDPOINT environment variable is required."),
        ):
            response = await client.post(
                "/chat",
                json={"message": "What is my balance?", "session_id": "err-1"},
            )

        assert response.status_code == 500
        assert "FOUNDRY_PROJECT_ENDPOINT" in response.json()["detail"]

    async def test_returns_500_on_unexpected_error(
        self, client: AsyncClient
    ) -> None:
        """POST /chat must return 500 when run_query raises an unexpected error."""
        with patch(
            "api.chat.run_query",
            new_callable=AsyncMock,
            side_effect=RuntimeError("unexpected"),
        ):
            response = await client.post(
                "/chat",
                json={"message": "Crash!", "session_id": "err-2"},
            )

        assert response.status_code == 500
        assert "Agent error" in response.json()["detail"]

    async def test_returns_422_on_missing_message(
        self, client: AsyncClient
    ) -> None:
        """POST /chat must return 422 when the message field is absent."""
        response = await client.post("/chat", json={"session_id": "s"})

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    async def test_health_check_returns_ok(self, client: AsyncClient) -> None:
        """GET /health must return {"status": "ok"}."""
        response = await client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
