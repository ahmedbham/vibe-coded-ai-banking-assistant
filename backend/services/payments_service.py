"""Mock Payments Service – standalone FastAPI application.

Run with:
    uvicorn backend.services.payments_service:app --port 8002 --reload
"""

import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="Payments Service",
    description="Mock Payments Service for the Banking Assistant",
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# In-memory store for submitted payments (used for duplicate detection)
# ---------------------------------------------------------------------------

_PAYMENTS: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class PaymentRequest(BaseModel):
    account_id: str
    beneficiary_id: str
    amount: float
    currency: str
    reference: str


class PaymentResponse(BaseModel):
    confirmation_id: str
    account_id: str
    beneficiary_id: str
    amount: float
    currency: str
    reference: str
    status: str
    timestamp: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/payments", status_code=201)
async def submit_payment(payment: PaymentRequest) -> PaymentResponse:
    """Submit a payment and return a confirmation ID."""
    if payment.amount <= 0:
        raise HTTPException(
            status_code=422,
            detail="amount must be greater than zero",
        )

    # Duplicate detection: same account_id + reference already processed
    duplicate_key = f"{payment.account_id}:{payment.reference}"
    if duplicate_key in _PAYMENTS:
        raise HTTPException(
            status_code=409,
            detail=f"Duplicate payment: reference '{payment.reference}' already submitted for account '{payment.account_id}'",
        )

    confirmation_id = str(uuid.uuid4())
    record: dict = {
        "confirmation_id": confirmation_id,
        "account_id": payment.account_id,
        "beneficiary_id": payment.beneficiary_id,
        "amount": payment.amount,
        "currency": payment.currency,
        "reference": payment.reference,
        "status": "confirmed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _PAYMENTS[duplicate_key] = record
    return PaymentResponse(**record)
