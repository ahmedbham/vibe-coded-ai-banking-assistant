"""Tests for the Transactions MCP server tools.

Each test uses the FastMCP in-process Client and patches the HTTP transport
so that requests are served by the mock transactions service FastAPI app directly.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from fastmcp import Client

import mcp.transactions_mcp as transactions_mcp_module
from mcp.transactions_mcp import mcp
from services.transactions_service import app as transactions_app


@pytest.fixture(autouse=True)
def patch_transactions_http_client(monkeypatch):
    """Route MCP tool HTTP calls to the in-process transactions service."""

    def mock_get_client() -> AsyncClient:
        return AsyncClient(
            transport=ASGITransport(app=transactions_app), base_url="http://test"
        )

    monkeypatch.setattr(
        transactions_mcp_module, "_get_client", mock_get_client
    )


# ---------------------------------------------------------------------------
# searchTransactions
# ---------------------------------------------------------------------------


async def test_searchTransactions_with_query() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "searchTransactions", {"query": "coffee"}
        )
    data = result.data
    assert isinstance(data, list)
    assert len(data) > 0
    for txn in data:
        assert (
            "coffee" in txn["description"].lower()
            or "coffee" in txn["category"].lower()
        )


async def test_searchTransactions_no_results() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "searchTransactions", {"query": "zzznomatch"}
        )
    assert result.data == []


async def test_searchTransactions_no_query_returns_all() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("searchTransactions", {})
    data = result.data
    assert isinstance(data, list)
    assert len(data) > 0


# ---------------------------------------------------------------------------
# getTransactionByRecipient
# ---------------------------------------------------------------------------


async def test_getTransactionByRecipient_happy_path() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "getTransactionByRecipient", {"recipient_id": "RCP001"}
        )
    data = result.data
    assert isinstance(data, list)
    assert len(data) > 0
    for txn in data:
        assert txn["recipient_id"] == "RCP001"
        assert "transaction_id" in txn
        assert "amount" in txn


async def test_getTransactionByRecipient_not_found() -> None:
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool(
                "getTransactionByRecipient", {"recipient_id": "INVALID"}
            )


# ---------------------------------------------------------------------------
# notifyTransaction
# ---------------------------------------------------------------------------


async def test_notifyTransaction_happy_path() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "notifyTransaction",
            {
                "account_id": "ACC001",
                "recipient_id": "RCP099",
                "amount": 25.00,
                "description": "test mcp payment",
            },
        )
    data = result.data
    assert data["account_id"] == "ACC001"
    assert data["recipient_id"] == "RCP099"
    assert data["amount"] == 25.00
    assert data["status"] == "pending"
    assert "transaction_id" in data
    assert "timestamp" in data


async def test_notifyTransaction_defaults() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "notifyTransaction",
            {
                "account_id": "ACC002",
                "recipient_id": "RCP010",
                "amount": 50.00,
                "description": "default currency test",
            },
        )
    data = result.data
    assert data["currency"] == "USD"
    assert data["category"] == "other"
