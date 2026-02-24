"""Account MCP Server – exposes account service operations as MCP tools.

Run with:
    python -m mcp.account_mcp
or via FastMCP HTTP transport on port 9001:
    uvicorn mcp.account_mcp:http_app --port 9001
"""

import os

import httpx
from fastmcp import FastMCP

ACCOUNT_SERVICE_URL = os.getenv("ACCOUNT_SERVICE_URL", "http://localhost:8001")

mcp = FastMCP(
    "Account MCP Server",
    instructions="Provides account management tools for the banking assistant.",
)


def _get_client() -> httpx.AsyncClient:
    """Return an httpx async client pointed at the account service."""
    return httpx.AsyncClient(base_url=ACCOUNT_SERVICE_URL)


@mcp.tool()
async def getAccountByUsername(username: str) -> dict:
    """Return account information for the given username."""
    async with _get_client() as client:
        response = await client.get(f"/accounts/{username}")
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def getAccountDetails(account_id: str) -> dict:
    """Return detailed account information for the given account ID."""
    async with _get_client() as client:
        response = await client.get(f"/accounts/{account_id}/details")
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def getPaymentMethods(account_id: str) -> list:
    """Return payment methods registered for the given account ID."""
    async with _get_client() as client:
        response = await client.get(f"/accounts/{account_id}/payment-methods")
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def getRegisteredBeneficiaries(account_id: str) -> list:
    """Return registered beneficiaries for the given account ID."""
    async with _get_client() as client:
        response = await client.get(f"/accounts/{account_id}/beneficiaries")
        response.raise_for_status()
        return response.json()


http_app = mcp.http_app()

if __name__ == "__main__":
    mcp.run_http_async(port=9001)
