"""Mock Account Service – standalone FastAPI application.

Run with:
    uvicorn backend.services.account_service:app --port 8001 --reload
"""

from fastapi import FastAPI, HTTPException

app = FastAPI(
    title="Account Service",
    description="Mock Account Service for the Banking Assistant",
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# In-memory mock data
# ---------------------------------------------------------------------------

_ACCOUNTS: dict[str, dict] = {
    "john_doe": {
        "account_id": "ACC001",
        "username": "john_doe",
        "full_name": "John Doe",
        "email": "john.doe@example.com",
    },
    "jane_smith": {
        "account_id": "ACC002",
        "username": "jane_smith",
        "full_name": "Jane Smith",
        "email": "jane.smith@example.com",
    },
}

_ACCOUNT_DETAILS: dict[str, dict] = {
    "ACC001": {
        "account_id": "ACC001",
        "account_type": "checking",
        "balance": 2500.00,
        "currency": "USD",
        "status": "active",
    },
    "ACC002": {
        "account_id": "ACC002",
        "account_type": "savings",
        "balance": 10000.00,
        "currency": "USD",
        "status": "active",
    },
}

_PAYMENT_METHODS: dict[str, list[dict]] = {
    "ACC001": [
        {
            "payment_method_id": "PM001",
            "type": "debit_card",
            "last4": "1234",
            "brand": "Visa",
        },
        {
            "payment_method_id": "PM002",
            "type": "credit_card",
            "last4": "5678",
            "brand": "Mastercard",
        },
    ],
    "ACC002": [
        {
            "payment_method_id": "PM003",
            "type": "debit_card",
            "last4": "9012",
            "brand": "Visa",
        },
    ],
}

_BENEFICIARIES: dict[str, list[dict]] = {
    "ACC001": [
        {
            "beneficiary_id": "BEN001",
            "name": "Alice Johnson",
            "account_number": "987654321",
            "bank": "Chase",
        },
        {
            "beneficiary_id": "BEN002",
            "name": "Bob Williams",
            "account_number": "123456789",
            "bank": "Wells Fargo",
        },
    ],
    "ACC002": [
        {
            "beneficiary_id": "BEN003",
            "name": "Carol Davis",
            "account_number": "456789123",
            "bank": "Bank of America",
        },
    ],
}

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/accounts/{username}")
async def get_account_by_username(username: str) -> dict:
    """Return account information for the given username."""
    account = _ACCOUNTS.get(username)
    if account is None:
        raise HTTPException(
            status_code=404,
            detail=f"Account not found for username: {username}",
        )
    return account


@app.get("/accounts/{account_id}/details")
async def get_account_details(account_id: str) -> dict:
    """Return detailed account information for the given account ID."""
    details = _ACCOUNT_DETAILS.get(account_id)
    if details is None:
        raise HTTPException(
            status_code=404,
            detail=f"Account details not found for account_id: {account_id}",
        )
    return details


@app.get("/accounts/{account_id}/payment-methods")
async def get_payment_methods(account_id: str) -> list[dict]:
    """Return payment methods registered for the given account ID."""
    if account_id not in _ACCOUNT_DETAILS:
        raise HTTPException(
            status_code=404,
            detail=f"Account not found for account_id: {account_id}",
        )
    return _PAYMENT_METHODS.get(account_id, [])


@app.get("/accounts/{account_id}/beneficiaries")
async def get_registered_beneficiaries(account_id: str) -> list[dict]:
    """Return registered beneficiaries for the given account ID."""
    if account_id not in _ACCOUNT_DETAILS:
        raise HTTPException(
            status_code=404,
            detail=f"Account not found for account_id: {account_id}",
        )
    return _BENEFICIARIES.get(account_id, [])
