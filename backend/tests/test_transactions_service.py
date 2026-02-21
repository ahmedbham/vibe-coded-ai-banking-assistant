"""Unit tests for the mock Transactions Service."""

import pytest
from httpx import ASGITransport, AsyncClient

from services.transactions_service import app, _TRANSACTIONS


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# GET /transactions/search
# ---------------------------------------------------------------------------


async def test_search_transactions_with_query(client: AsyncClient) -> None:
    response = await client.get("/transactions/search?query=coffee")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    for txn in data:
        assert "coffee" in txn["description"].lower() or "coffee" in txn["category"].lower()


async def test_search_transactions_no_results(client: AsyncClient) -> None:
    response = await client.get("/transactions/search?query=zzznomatch")
    assert response.status_code == 200
    data = response.json()
    assert data == []


async def test_search_transactions_no_query_returns_all(client: AsyncClient) -> None:
    response = await client.get("/transactions/search")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == len(_TRANSACTIONS)


# ---------------------------------------------------------------------------
# GET /transactions/by-recipient/{recipient_id}
# ---------------------------------------------------------------------------


async def test_get_transactions_by_recipient_happy_path(client: AsyncClient) -> None:
    response = await client.get("/transactions/by-recipient/RCP001")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    for txn in data:
        assert txn["recipient_id"] == "RCP001"
        assert "transaction_id" in txn
        assert "amount" in txn


async def test_get_transactions_by_recipient_not_found(client: AsyncClient) -> None:
    response = await client.get("/transactions/by-recipient/INVALID")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /transactions/notify
# ---------------------------------------------------------------------------


async def test_notify_transaction_happy_path(client: AsyncClient) -> None:
    payload = {
        "account_id": "ACC001",
        "recipient_id": "RCP099",
        "amount": 25.00,
        "currency": "USD",
        "description": "test payment",
        "category": "other",
    }
    response = await client.post("/transactions/notify", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["account_id"] == "ACC001"
    assert data["recipient_id"] == "RCP099"
    assert data["amount"] == 25.00
    assert data["status"] == "pending"
    assert "transaction_id" in data
    assert "timestamp" in data


async def test_notify_transaction_missing_required_fields(client: AsyncClient) -> None:
    response = await client.post("/transactions/notify", json={"amount": 10.00})
    assert response.status_code == 422


async def test_notify_transaction_defaults(client: AsyncClient) -> None:
    payload = {
        "account_id": "ACC002",
        "recipient_id": "RCP010",
        "amount": 50.00,
        "description": "default currency test",
    }
    response = await client.post("/transactions/notify", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["currency"] == "USD"
    assert data["category"] == "other"
