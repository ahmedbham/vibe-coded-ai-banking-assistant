"""Unit tests for the mock Payments Service."""

import pytest
from httpx import ASGITransport, AsyncClient

from services.payments_service import app, _PAYMENTS


@pytest.fixture(autouse=True)
def clear_payments():
    """Reset the in-memory payments store before each test."""
    _PAYMENTS.clear()
    yield
    _PAYMENTS.clear()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


_VALID_PAYLOAD = {
    "account_id": "ACC001",
    "beneficiary_id": "BEN001",
    "amount": 150.00,
    "currency": "USD",
    "reference": "INV-2024-001",
}

# ---------------------------------------------------------------------------
# POST /payments – success
# ---------------------------------------------------------------------------


async def test_submit_payment_success(client: AsyncClient) -> None:
    response = await client.post("/payments", json=_VALID_PAYLOAD)
    assert response.status_code == 201
    data = response.json()
    assert "confirmation_id" in data
    assert data["confirmation_id"] != ""
    assert data["account_id"] == _VALID_PAYLOAD["account_id"]
    assert data["beneficiary_id"] == _VALID_PAYLOAD["beneficiary_id"]
    assert data["amount"] == _VALID_PAYLOAD["amount"]
    assert data["currency"] == _VALID_PAYLOAD["currency"]
    assert data["reference"] == _VALID_PAYLOAD["reference"]
    assert data["status"] == "confirmed"
    assert "timestamp" in data


# ---------------------------------------------------------------------------
# POST /payments – missing / invalid fields
# ---------------------------------------------------------------------------


async def test_submit_payment_missing_account_id(client: AsyncClient) -> None:
    payload = {k: v for k, v in _VALID_PAYLOAD.items() if k != "account_id"}
    response = await client.post("/payments", json=payload)
    assert response.status_code == 422


async def test_submit_payment_missing_beneficiary_id(client: AsyncClient) -> None:
    payload = {k: v for k, v in _VALID_PAYLOAD.items() if k != "beneficiary_id"}
    response = await client.post("/payments", json=payload)
    assert response.status_code == 422


async def test_submit_payment_missing_amount(client: AsyncClient) -> None:
    payload = {k: v for k, v in _VALID_PAYLOAD.items() if k != "amount"}
    response = await client.post("/payments", json=payload)
    assert response.status_code == 422


async def test_submit_payment_missing_reference(client: AsyncClient) -> None:
    payload = {k: v for k, v in _VALID_PAYLOAD.items() if k != "reference"}
    response = await client.post("/payments", json=payload)
    assert response.status_code == 422


async def test_submit_payment_zero_amount(client: AsyncClient) -> None:
    payload = {**_VALID_PAYLOAD, "amount": 0}
    response = await client.post("/payments", json=payload)
    assert response.status_code == 422


async def test_submit_payment_negative_amount(client: AsyncClient) -> None:
    payload = {**_VALID_PAYLOAD, "amount": -50.00}
    response = await client.post("/payments", json=payload)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /payments – duplicate detection
# ---------------------------------------------------------------------------


async def test_submit_payment_duplicate(client: AsyncClient) -> None:
    first = await client.post("/payments", json=_VALID_PAYLOAD)
    assert first.status_code == 201

    second = await client.post("/payments", json=_VALID_PAYLOAD)
    assert second.status_code == 409
    assert "Duplicate payment" in second.json()["detail"]


async def test_submit_payment_different_reference_not_duplicate(
    client: AsyncClient,
) -> None:
    payload_a = {**_VALID_PAYLOAD, "reference": "REF-001"}
    payload_b = {**_VALID_PAYLOAD, "reference": "REF-002"}

    resp_a = await client.post("/payments", json=payload_a)
    resp_b = await client.post("/payments", json=payload_b)

    assert resp_a.status_code == 201
    assert resp_b.status_code == 201
    # Confirmation IDs must be distinct
    assert resp_a.json()["confirmation_id"] != resp_b.json()["confirmation_id"]
