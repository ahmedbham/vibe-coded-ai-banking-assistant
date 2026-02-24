"""Document MCP Server – exposes Azure Document Intelligence as MCP tools.

Run with:
    python -m mcp.document_mcp
or via FastMCP HTTP transport on port 9004:
    uvicorn mcp.document_mcp:http_app --port 9004
"""

import os
from dataclasses import dataclass

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.identity import DefaultAzureCredential
from fastmcp import FastMCP

DOCUMENT_INTELLIGENCE_ENDPOINT = os.getenv("DOCUMENT_INTELLIGENCE_ENDPOINT", "")

mcp = FastMCP(
    "Document MCP Server",
    instructions="Provides document scanning tools for the banking assistant.",
)


@dataclass
class InvoiceData:
    """Extracted fields from a scanned invoice."""

    vendor_name: str | None
    vendor_address: str | None
    invoice_id: str | None
    invoice_date: str | None
    due_date: str | None
    amount_due: float | None
    currency: str | None
    line_items: list[dict]


def _get_document_intelligence_client() -> DocumentIntelligenceClient:
    """Return an Azure Document Intelligence client using DefaultAzureCredential."""
    credential = DefaultAzureCredential()
    return DocumentIntelligenceClient(
        endpoint=DOCUMENT_INTELLIGENCE_ENDPOINT, credential=credential
    )


def _extract_invoice_data(result) -> InvoiceData:
    """Extract structured invoice fields from the Document Intelligence result."""
    if not result.documents:
        return InvoiceData(
            vendor_name=None,
            vendor_address=None,
            invoice_id=None,
            invoice_date=None,
            due_date=None,
            amount_due=None,
            currency=None,
            line_items=[],
        )

    doc = result.documents[0]
    fields = doc.get("fields", {}) if isinstance(doc, dict) else (doc.fields or {})

    def _str_field(name: str) -> str | None:
        field = fields.get(name)
        if field is None:
            return None
        value = field.get("valueString") or field.get("content")
        return str(value) if value is not None else None

    def _date_field(name: str) -> str | None:
        field = fields.get(name)
        if field is None:
            return None
        value = field.get("valueDate") or field.get("content")
        return str(value) if value is not None else None

    def _amount_field(name: str) -> tuple[float | None, str | None]:
        field = fields.get(name)
        if field is None:
            return None, None
        value_currency = field.get("valueCurrency")
        if value_currency:
            return value_currency.get("amount"), value_currency.get("currencyCode")
        content = field.get("content")
        return (float(content) if content is not None else None), None

    amount_due, currency = _amount_field("InvoiceTotal")

    # Extract line items
    line_items: list[dict] = []
    items_field = fields.get("Items")
    if items_field:
        items_list = items_field.get("valueArray")
        if items_list is None:
            items_list = items_field.get("valueList")
        if items_list is None:
            items_list = []
        for item in items_list:
            item_fields = item.get("valueObject")
            if item_fields is None:
                item_fields = item.get("fields")
            if item_fields is None:
                item_fields = {}
            description_field = item_fields.get("Description")
            amount_field = item_fields.get("Amount")

            description = None
            if description_field:
                val = description_field.get("valueString")
                if val is None:
                    val = description_field.get("content")
                description = val

            item_amount = None
            if amount_field:
                value_currency = amount_field.get("valueCurrency")
                if value_currency:
                    item_amount = value_currency.get("amount")
                else:
                    item_amount = amount_field.get("content")

            line_items.append({"description": description, "amount": item_amount})

    return InvoiceData(
        vendor_name=_str_field("VendorName"),
        vendor_address=_str_field("VendorAddress"),
        invoice_id=_str_field("InvoiceId"),
        invoice_date=_date_field("InvoiceDate"),
        due_date=_date_field("DueDate"),
        amount_due=amount_due,
        currency=currency,
        line_items=line_items,
    )


@mcp.tool()
async def scanInvoice(file_url: str) -> dict:
    """Scan an invoice image or PDF from the given URL and return extracted fields.

    Args:
        file_url: A publicly accessible URL to the invoice image or PDF.

    Returns:
        A dictionary with extracted invoice fields including vendor name, address,
        invoice ID, invoice date, due date, amount due, currency, and line items.
    """
    client = _get_document_intelligence_client()
    poller = client.begin_analyze_document(
        "prebuilt-invoice",
        AnalyzeDocumentRequest(url_source=file_url),
    )
    result = poller.result()
    invoice_data = _extract_invoice_data(result)
    return {
        "vendor_name": invoice_data.vendor_name,
        "vendor_address": invoice_data.vendor_address,
        "invoice_id": invoice_data.invoice_id,
        "invoice_date": invoice_data.invoice_date,
        "due_date": invoice_data.due_date,
        "amount_due": invoice_data.amount_due,
        "currency": invoice_data.currency,
        "line_items": invoice_data.line_items,
    }


http_app = mcp.http_app()

if __name__ == "__main__":
    mcp.run_http_async(port=9004)
