# Azure Document Intelligence – Setup Guide

This guide explains how to provision the Azure Document Intelligence resource required by the `scanInvoice` MCP tool and configure the backend service to use it.

---

## Prerequisites

- An active Azure subscription
- Azure CLI (`az`) installed and authenticated (`az login`)
- Contributor or Owner role on the target subscription / resource group

---

## 1. Create a Resource Group (if needed)

```bash
az group create \
  --name rg-banking-assistant \
  --location eastus
```

---

## 2. Provision Azure Document Intelligence

```bash
az cognitiveservices account create \
  --name doc-intel-banking-assistant \
  --resource-group rg-banking-assistant \
  --kind FormRecognizer \
  --sku S0 \
  --location eastus \
  --yes
```

> **Note:** The `FormRecognizer` kind is the Azure resource type for Document Intelligence.  
> The `S0` SKU supports the `prebuilt-invoice` model used by the `scanInvoice` tool.

---

## 3. Retrieve the Endpoint

```bash
az cognitiveservices account show \
  --name doc-intel-banking-assistant \
  --resource-group rg-banking-assistant \
  --query properties.endpoint \
  --output tsv
```

Copy the endpoint URL (e.g. `https://doc-intel-banking-assistant.cognitiveservices.azure.com/`).

---

## 4. Grant Access via Managed Identity

The `scanInvoice` tool authenticates using `DefaultAzureCredential` (Managed Identity in Azure Container Apps or the developer's Azure CLI credentials locally).  
Assign the **Cognitive Services User** role to the identity that will run the Document MCP service:

```bash
# Replace <PRINCIPAL_ID> with your Container App's managed identity object ID
# or your own Azure AD object ID for local development.
az role assignment create \
  --assignee <PRINCIPAL_ID> \
  --role "Cognitive Services User" \
  --scope $(az cognitiveservices account show \
              --name doc-intel-banking-assistant \
              --resource-group rg-banking-assistant \
              --query id --output tsv)
```

---

## 5. Configure the Backend Service

Set the following environment variable for the Document MCP service container:

| Variable | Description | Example |
|---|---|---|
| `DOCUMENT_INTELLIGENCE_ENDPOINT` | Full endpoint URL of the Document Intelligence resource | `https://doc-intel-banking-assistant.cognitiveservices.azure.com/` |

### Local development (`.env` or shell)

```bash
export DOCUMENT_INTELLIGENCE_ENDPOINT="https://doc-intel-banking-assistant.cognitiveservices.azure.com/"
```

### Azure Container Apps (via `az containerapp update`)

```bash
az containerapp update \
  --name document-mcp \
  --resource-group rg-banking-assistant \
  --set-env-vars DOCUMENT_INTELLIGENCE_ENDPOINT=https://doc-intel-banking-assistant.cognitiveservices.azure.com/
```

---

## 6. Run the Document MCP Service

```bash
# From backend/
uvicorn mcp.document_mcp:http_app --port 9004
```

---

## 7. Verify with a Test Invoice

```bash
curl -X POST http://localhost:9004/tools/scanInvoice \
  -H "Content-Type: application/json" \
  -d '{"file_url": "https://raw.githubusercontent.com/Azure-Samples/cognitive-services-REST-api-samples/master/curl/form-recognizer/invoice_sample.jpg"}'
```

A successful response looks like:

```json
{
  "vendor_name": "Contoso",
  "vendor_address": "123 456th St New York, NY, 10001",
  "invoice_id": "INV-100",
  "invoice_date": "2019-11-15",
  "due_date": "2019-12-15",
  "amount_due": 610.00,
  "currency": "USD",
  "line_items": [
    {"description": "Test for invoice", "amount": 610.00}
  ]
}
```

---

## 8. Running the Unit Tests

The unit tests mock all Azure SDK calls and do **not** require a provisioned resource:

```bash
cd backend/
pytest tests/test_document_mcp.py -v
```

---

## Security Notes

- **No API keys in source code.** The `scanInvoice` tool uses `DefaultAzureCredential`; no key is stored or logged.
- **Managed Identity only.** Assign only the minimum required role (`Cognitive Services User`).
- **No PII in logs.** The tool does not log invoice content or URLs.
