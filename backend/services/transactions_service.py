"""Mock Transactions/Reporting Service – standalone FastAPI application.

Run with:
    uvicorn backend.services.transactions_service:app --port 8003 --reload
"""

from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="Transactions Service",
    description="Mock Transactions/Reporting Service for the Banking Assistant",
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# In-memory mock data
# ---------------------------------------------------------------------------

_TRANSACTIONS: list[dict] = [
    {
        "transaction_id": "TXN001",
        "account_id": "ACC001",
        "recipient_id": "RCP001",
        "amount": 4.50,
        "currency": "USD",
        "description": "coffee shop",
        "category": "food_and_drink",
        "status": "completed",
        "timestamp": "2024-01-15T08:30:00Z",
    },
    {
        "transaction_id": "TXN002",
        "account_id": "ACC001",
        "recipient_id": "RCP002",
        "amount": 120.00,
        "currency": "USD",
        "description": "electricity bill payment",
        "category": "utilities",
        "status": "completed",
        "timestamp": "2024-01-14T17:00:00Z",
    },
    {
        "transaction_id": "TXN003",
        "account_id": "ACC002",
        "recipient_id": "RCP001",
        "amount": 8.75,
        "currency": "USD",
        "description": "coffee and pastry",
        "category": "food_and_drink",
        "status": "completed",
        "timestamp": "2024-01-15T09:00:00Z",
    },
    {
        "transaction_id": "TXN004",
        "account_id": "ACC001",
        "recipient_id": "RCP003",
        "amount": 55.00,
        "currency": "USD",
        "description": "grocery store",
        "category": "groceries",
        "status": "completed",
        "timestamp": "2024-01-13T12:00:00Z",
    },
    {
        "transaction_id": "TXN005",
        "account_id": "ACC002",
        "recipient_id": "RCP004",
        "amount": 200.00,
        "currency": "USD",
        "description": "rent payment",
        "category": "housing",
        "status": "pending",
        "timestamp": "2024-01-15T10:00:00Z",
    },
]

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class TransactionNotification(BaseModel):
    account_id: str
    recipient_id: str
    amount: float
    currency: str = "USD"
    description: str
    category: str = "other"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/transactions/notify", status_code=201)
async def notify_transaction(notification: TransactionNotification) -> dict:
    """Record a new transaction notification."""
    new_id = f"TXN{len(_TRANSACTIONS) + 1:03d}"
    transaction = {
        "transaction_id": new_id,
        "account_id": notification.account_id,
        "recipient_id": notification.recipient_id,
        "amount": notification.amount,
        "currency": notification.currency,
        "description": notification.description,
        "category": notification.category,
        "status": "pending",
        "timestamp": datetime.now(UTC).isoformat(),
    }
    _TRANSACTIONS.append(transaction)
    return transaction


@app.get("/transactions/search")
async def search_transactions(query: str = "") -> list[dict]:
    """Search transactions by keyword in description or category."""
    if not query:
        return _TRANSACTIONS
    q = query.lower()
    return [
        txn
        for txn in _TRANSACTIONS
        if q in txn["description"].lower() or q in txn["category"].lower()
    ]


@app.get("/transactions/by-recipient/{recipient_id}")
async def get_transactions_by_recipient(recipient_id: str) -> list[dict]:
    """Return all transactions for the given recipient ID."""
    results = [txn for txn in _TRANSACTIONS if txn["recipient_id"] == recipient_id]
    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No transactions found for recipient_id: {recipient_id}",
        )
    return results
