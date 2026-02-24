"""Tests for the Account MCP server tools.

Each test uses the FastMCP in-process Client and patches the HTTP transport
so that requests are served by the mock account service FastAPI app directly.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from fastmcp import Client

import mcp.account_mcp as account_mcp_module
from mcp.account_mcp import mcp
from services.account_service import app as account_app


@pytest.fixture(autouse=True)
def patch_account_http_client(monkeypatch):
    """Route MCP tool HTTP calls to the in-process account service."""

    def mock_get_client() -> AsyncClient:
        return AsyncClient(
            transport=ASGITransport(app=account_app), base_url="http://test"
        )

    monkeypatch.setattr(account_mcp_module, "_get_client", mock_get_client)


# ---------------------------------------------------------------------------
# getAccountByUsername
# ---------------------------------------------------------------------------


async def test_getAccountByUsername_happy_path() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "getAccountByUsername", {"username": "john_doe"}
        )
    data = result.data
    assert data["username"] == "john_doe"
    assert data["account_id"] == "ACC001"
    assert "full_name" in data
    assert "email" in data


async def test_getAccountByUsername_not_found() -> None:
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool(
                "getAccountByUsername", {"username": "nonexistent_user"}
            )


# ---------------------------------------------------------------------------
# getAccountDetails
# ---------------------------------------------------------------------------


async def test_getAccountDetails_happy_path() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "getAccountDetails", {"account_id": "ACC001"}
        )
    data = result.data
    assert data["account_id"] == "ACC001"
    assert "balance" in data
    assert "account_type" in data
    assert "currency" in data
    assert "status" in data


async def test_getAccountDetails_not_found() -> None:
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool(
                "getAccountDetails", {"account_id": "INVALID"}
            )


# ---------------------------------------------------------------------------
# getPaymentMethods
# ---------------------------------------------------------------------------


async def test_getPaymentMethods_happy_path() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "getPaymentMethods", {"account_id": "ACC001"}
        )
    data = result.data
    assert isinstance(data, list)
    assert len(data) > 0
    assert "payment_method_id" in data[0]
    assert "type" in data[0]


async def test_getPaymentMethods_not_found() -> None:
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool(
                "getPaymentMethods", {"account_id": "INVALID"}
            )


# ---------------------------------------------------------------------------
# getRegisteredBeneficiaries
# ---------------------------------------------------------------------------


async def test_getRegisteredBeneficiaries_happy_path() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "getRegisteredBeneficiaries", {"account_id": "ACC001"}
        )
    data = result.data
    assert isinstance(data, list)
    assert len(data) > 0
    assert "beneficiary_id" in data[0]
    assert "name" in data[0]


async def test_getRegisteredBeneficiaries_not_found() -> None:
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool(
                "getRegisteredBeneficiaries", {"account_id": "INVALID"}
            )
