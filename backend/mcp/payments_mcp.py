"""Payments MCP Server – exposes payment service operations as MCP tools.

Run with:
    python -m mcp.payments_mcp
or via FastMCP HTTP transport on port 9003:
    uvicorn mcp.payments_mcp:http_app --port 9003
"""

import os

import httpx
from fastmcp import FastMCP

PAYMENTS_SERVICE_URL = os.getenv("PAYMENTS_SERVICE_URL", "http://localhost:8002")

mcp = FastMCP(
    "Payments MCP Server",
    instructions="Provides payment submission tools for the banking assistant.",
)


def _get_client() -> httpx.AsyncClient:
    """Return an httpx async client pointed at the payments service."""
    return httpx.AsyncClient(base_url=PAYMENTS_SERVICE_URL)


@mcp.tool()
async def submitPayment(
    account_id: str,
    beneficiary_id: str,
    amount: float,
    currency: str,
    reference: str,
) -> dict:
    """Submit a payment and return a confirmation record."""
    payload = {
        "account_id": account_id,
        "beneficiary_id": beneficiary_id,
        "amount": amount,
        "currency": currency,
        "reference": reference,
    }
    async with _get_client() as client:
        response = await client.post("/payments", json=payload)
        response.raise_for_status()
        return response.json()


http_app = mcp.http_app()

if __name__ == "__main__":
    mcp.run_http_async(port=9003)
