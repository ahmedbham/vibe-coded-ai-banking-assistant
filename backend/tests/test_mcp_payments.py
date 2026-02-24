"""Tests for the Payments MCP server tools.

Each test uses the FastMCP in-process Client and patches the HTTP transport
so that requests are served by the mock payments service FastAPI app directly.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from fastmcp import Client

import mcp.payments_mcp as payments_mcp_module
from mcp.payments_mcp import mcp
from services.payments_service import app as payments_app, _PAYMENTS


@pytest.fixture(autouse=True)
def clear_payments():
    """Reset the in-memory payments store before and after each test."""
    _PAYMENTS.clear()
    yield
    _PAYMENTS.clear()


@pytest.fixture(autouse=True)
def patch_payments_http_client(monkeypatch):
    """Route MCP tool HTTP calls to the in-process payments service."""

    def mock_get_client() -> AsyncClient:
        return AsyncClient(
            transport=ASGITransport(app=payments_app), base_url="http://test"
        )

    monkeypatch.setattr(payments_mcp_module, "_get_client", mock_get_client)


_VALID_ARGS = {
    "account_id": "ACC001",
    "beneficiary_id": "BEN001",
    "amount": 150.00,
    "currency": "USD",
    "reference": "INV-MCP-001",
}

# ---------------------------------------------------------------------------
# submitPayment – success
# ---------------------------------------------------------------------------


async def test_submitPayment_success() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("submitPayment", _VALID_ARGS)
    data = result.data
    assert "confirmation_id" in data
    assert data["confirmation_id"] != ""
    assert data["account_id"] == _VALID_ARGS["account_id"]
    assert data["beneficiary_id"] == _VALID_ARGS["beneficiary_id"]
    assert data["amount"] == _VALID_ARGS["amount"]
    assert data["currency"] == _VALID_ARGS["currency"]
    assert data["reference"] == _VALID_ARGS["reference"]
    assert data["status"] == "confirmed"
    assert "timestamp" in data


# ---------------------------------------------------------------------------
# submitPayment – invalid amount
# ---------------------------------------------------------------------------


async def test_submitPayment_zero_amount() -> None:
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool(
                "submitPayment", {**_VALID_ARGS, "amount": 0}
            )


async def test_submitPayment_negative_amount() -> None:
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool(
                "submitPayment", {**_VALID_ARGS, "amount": -50.00}
            )


# ---------------------------------------------------------------------------
# submitPayment – duplicate detection
# ---------------------------------------------------------------------------


async def test_submitPayment_duplicate() -> None:
    async with Client(mcp) as client:
        first = await client.call_tool("submitPayment", _VALID_ARGS)
        assert first.data["status"] == "confirmed"

        with pytest.raises(Exception):
            await client.call_tool("submitPayment", _VALID_ARGS)


async def test_submitPayment_different_reference_not_duplicate() -> None:
    async with Client(mcp) as client:
        result_a = await client.call_tool(
            "submitPayment", {**_VALID_ARGS, "reference": "REF-MCP-001"}
        )
        result_b = await client.call_tool(
            "submitPayment", {**_VALID_ARGS, "reference": "REF-MCP-002"}
        )
    assert result_a.data["status"] == "confirmed"
    assert result_b.data["status"] == "confirmed"
    assert result_a.data["confirmation_id"] != result_b.data["confirmation_id"]
