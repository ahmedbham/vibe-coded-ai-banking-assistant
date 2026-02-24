"""Transactions MCP Server – exposes transaction service operations as MCP tools.

Run with:
    python -m mcp.transactions_mcp
or via FastMCP HTTP transport on port 9002:
    uvicorn mcp.transactions_mcp:http_app --port 9002
"""

import os

import httpx
from fastmcp import FastMCP

TRANSACTIONS_SERVICE_URL = os.getenv(
    "TRANSACTIONS_SERVICE_URL", "http://localhost:8003"
)

mcp = FastMCP(
    "Transactions MCP Server",
    instructions="Provides transaction management tools for the banking assistant.",
)


def _get_client() -> httpx.AsyncClient:
    """Return an httpx async client pointed at the transactions service."""
    return httpx.AsyncClient(base_url=TRANSACTIONS_SERVICE_URL)


@mcp.tool()
async def notifyTransaction(
    account_id: str,
    recipient_id: str,
    amount: float,
    description: str,
    currency: str = "USD",
    category: str = "other",
) -> dict:
    """Record a new transaction notification and return the created transaction."""
    payload = {
        "account_id": account_id,
        "recipient_id": recipient_id,
        "amount": amount,
        "currency": currency,
        "description": description,
        "category": category,
    }
    async with _get_client() as client:
        response = await client.post("/transactions/notify", json=payload)
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def searchTransactions(query: str = "") -> list:
    """Search transactions by keyword in description or category."""
    async with _get_client() as client:
        response = await client.get(
            "/transactions/search", params={"query": query} if query else {}
        )
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def getTransactionByRecipient(recipient_id: str) -> list:
    """Return all transactions for the given recipient ID."""
    async with _get_client() as client:
        response = await client.get(
            f"/transactions/by-recipient/{recipient_id}"
        )
        response.raise_for_status()
        return response.json()


http_app = mcp.http_app()

if __name__ == "__main__":
    mcp.run_http_async(port=9002)
