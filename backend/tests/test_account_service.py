"""Unit tests for the mock Account Service."""

import pytest
from httpx import ASGITransport, AsyncClient

from services.account_service import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# GET /accounts/{username}
# ---------------------------------------------------------------------------


async def test_get_account_by_username_happy_path(client: AsyncClient) -> None:
    response = await client.get("/accounts/john_doe")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "john_doe"
    assert data["account_id"] == "ACC001"
    assert "full_name" in data
    assert "email" in data


async def test_get_account_by_username_not_found(client: AsyncClient) -> None:
    response = await client.get("/accounts/unknown_user")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /accounts/{account_id}/details
# ---------------------------------------------------------------------------


async def test_get_account_details_happy_path(client: AsyncClient) -> None:
    response = await client.get("/accounts/ACC001/details")
    assert response.status_code == 200
    data = response.json()
    assert data["account_id"] == "ACC001"
    assert "balance" in data
    assert "account_type" in data


async def test_get_account_details_not_found(client: AsyncClient) -> None:
    response = await client.get("/accounts/INVALID/details")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /accounts/{account_id}/payment-methods
# ---------------------------------------------------------------------------


async def test_get_payment_methods_happy_path(client: AsyncClient) -> None:
    response = await client.get("/accounts/ACC001/payment-methods")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "payment_method_id" in data[0]


async def test_get_payment_methods_not_found(client: AsyncClient) -> None:
    response = await client.get("/accounts/INVALID/payment-methods")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /accounts/{account_id}/beneficiaries
# ---------------------------------------------------------------------------


async def test_get_registered_beneficiaries_happy_path(client: AsyncClient) -> None:
    response = await client.get("/accounts/ACC001/beneficiaries")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "beneficiary_id" in data[0]


async def test_get_registered_beneficiaries_not_found(client: AsyncClient) -> None:
    response = await client.get("/accounts/INVALID/beneficiaries")
    assert response.status_code == 404
