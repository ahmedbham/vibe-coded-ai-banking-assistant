"""Tests for the Document MCP server tools.

Each test mocks the Azure Document Intelligence SDK so no real Azure resource
is required to run the suite.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastmcp import Client

import mcp.document_mcp as document_mcp_module
from mcp.document_mcp import _extract_invoice_data, mcp


def _make_field(
    string_value=None,
    date_value=None,
    currency_amount=None,
    currency_code=None,
    content=None,
):
    """Build a minimal Document Intelligence field dict."""
    field: dict = {}
    if string_value is not None:
        field["valueString"] = string_value
    if date_value is not None:
        field["valueDate"] = date_value
    if currency_amount is not None:
        field["valueCurrency"] = {
            "amount": currency_amount,
            "currencyCode": currency_code,
        }
    if content is not None:
        field["content"] = content
    return field


def _make_result(fields: dict) -> MagicMock:
    """Build a minimal Document Intelligence AnalyzeResult mock."""
    doc = MagicMock()
    doc.fields = fields
    doc.__getitem__ = lambda self, key: {"fields": fields}[key]
    result = MagicMock()
    result.documents = [doc]
    return result


# ---------------------------------------------------------------------------
# _extract_invoice_data – unit tests
# ---------------------------------------------------------------------------


def _make_items_field(items: list[dict]) -> dict:
    """Build a minimal Items field dict containing the given list of item dicts."""
    return {"valueArray": items}


def test_extract_invoice_data_full():
    """All fields present and correctly extracted."""
    line_item = {
        "valueObject": {
            "Description": {"valueString": "Consulting services", "content": None},
            "Amount": {"valueCurrency": {"amount": 1500.00}},
        }
    }
    fields = {
        "VendorName": _make_field(string_value="Acme Corp"),
        "VendorAddress": _make_field(string_value="123 Main St, Springfield"),
        "InvoiceId": _make_field(string_value="INV-2024-001"),
        "InvoiceDate": _make_field(date_value="2024-01-15"),
        "DueDate": _make_field(date_value="2024-02-15"),
        "InvoiceTotal": _make_field(currency_amount=1500.00, currency_code="USD"),
        "Items": _make_items_field([line_item]),
    }
    result = _make_result(fields)
    data = _extract_invoice_data(result)

    assert data.vendor_name == "Acme Corp"
    assert data.vendor_address == "123 Main St, Springfield"
    assert data.invoice_id == "INV-2024-001"
    assert data.invoice_date == "2024-01-15"
    assert data.due_date == "2024-02-15"
    assert data.amount_due == 1500.00
    assert data.currency == "USD"


def test_extract_invoice_data_no_documents():
    """When no documents are found, all fields are None."""
    result = MagicMock()
    result.documents = []
    data = _extract_invoice_data(result)

    assert data.vendor_name is None
    assert data.vendor_address is None
    assert data.invoice_id is None
    assert data.invoice_date is None
    assert data.due_date is None
    assert data.amount_due is None
    assert data.currency is None
    assert data.line_items == []


def test_extract_invoice_data_missing_optional_fields():
    """Only required/present fields are populated; missing ones are None."""
    fields = {
        "VendorName": _make_field(string_value="Beta LLC"),
        "InvoiceTotal": _make_field(currency_amount=250.00, currency_code="EUR"),
    }
    result = _make_result(fields)
    data = _extract_invoice_data(result)

    assert data.vendor_name == "Beta LLC"
    assert data.vendor_address is None
    assert data.invoice_id is None
    assert data.invoice_date is None
    assert data.due_date is None
    assert data.amount_due == 250.00
    assert data.currency == "EUR"
    assert data.line_items == []


# ---------------------------------------------------------------------------
# scanInvoice MCP tool – patched Azure SDK
# ---------------------------------------------------------------------------


def _build_mock_poller(fields: dict) -> MagicMock:
    """Return a mock poller whose .result() yields a fake AnalyzeResult."""
    poller = MagicMock()
    poller.result.return_value = _make_result(fields)
    return poller


@pytest.fixture()
def patch_doc_intelligence(monkeypatch):
    """Replace _get_document_intelligence_client with a factory returning a mock."""

    def _factory(fields: dict):
        mock_client = MagicMock()
        mock_client.begin_analyze_document.return_value = _build_mock_poller(fields)
        monkeypatch.setattr(
            document_mcp_module,
            "_get_document_intelligence_client",
            lambda: mock_client,
        )
        return mock_client

    return _factory


async def test_scanInvoice_returns_expected_fields(patch_doc_intelligence) -> None:
    """scanInvoice tool returns correctly structured invoice data."""
    patch_doc_intelligence(
        {
            "VendorName": _make_field(string_value="Globex Inc"),
            "VendorAddress": _make_field(string_value="742 Evergreen Terrace"),
            "InvoiceId": _make_field(string_value="INV-9999"),
            "InvoiceDate": _make_field(date_value="2024-03-01"),
            "DueDate": _make_field(date_value="2024-04-01"),
            "InvoiceTotal": _make_field(currency_amount=999.99, currency_code="USD"),
        }
    )
    async with Client(mcp) as client:
        result = await client.call_tool(
            "scanInvoice", {"file_url": "https://example.com/invoice.pdf"}
        )
    data = result.data
    assert data["vendor_name"] == "Globex Inc"
    assert data["vendor_address"] == "742 Evergreen Terrace"
    assert data["invoice_id"] == "INV-9999"
    assert data["invoice_date"] == "2024-03-01"
    assert data["due_date"] == "2024-04-01"
    assert data["amount_due"] == 999.99
    assert data["currency"] == "USD"
    assert isinstance(data["line_items"], list)


async def test_scanInvoice_no_documents() -> None:
    """scanInvoice returns None fields when Document Intelligence finds nothing."""
    mock_client = MagicMock()
    empty_result = MagicMock()
    empty_result.documents = []
    mock_client.begin_analyze_document.return_value = MagicMock(
        **{"result.return_value": empty_result}
    )

    with patch.object(
        document_mcp_module,
        "_get_document_intelligence_client",
        return_value=mock_client,
    ):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "scanInvoice", {"file_url": "https://example.com/blank.pdf"}
            )
    data = result.data
    assert data["vendor_name"] is None
    assert data["amount_due"] is None
    assert data["line_items"] == []


async def test_scanInvoice_sdk_error_propagates(monkeypatch) -> None:
    """scanInvoice raises when the Azure SDK raises an exception."""
    mock_client = MagicMock()
    mock_client.begin_analyze_document.side_effect = RuntimeError("Azure SDK error")
    monkeypatch.setattr(
        document_mcp_module,
        "_get_document_intelligence_client",
        lambda: mock_client,
    )
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool(
                "scanInvoice", {"file_url": "https://example.com/invoice.pdf"}
            )
