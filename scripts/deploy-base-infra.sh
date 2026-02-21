#!/usr/bin/env bash
# deploy-base-infra.sh – Provision or update the shared Azure base infrastructure.
#
# Usage:
#   AZURE_RESOURCE_GROUP=rg-banking-dev \
#   AZURE_LOCATION=westus2 \
#   bash scripts/deploy-base-infra.sh
#
# Required environment variables:
#   AZURE_RESOURCE_GROUP  – Target resource group name (created if it does not exist).
#
# Optional environment variables:
#   AZURE_LOCATION        – Azure region  (default: westus2).
#   BICEP_PARAMS_FILE     – Path to parameters file (default: infra/parameters.dev.json).
#   ENVIRONMENT           – Short environment label: dev | staging | prod  (default: dev).
#   PROJECT               – Short project label (default: banking).
#   OWNER                 – Owner tag value (default: platform-team).

set -Eeuo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
: "${AZURE_RESOURCE_GROUP:=rg-banking-dev}"
: "${AZURE_LOCATION:=westus2}"
: "${BICEP_PARAMS_FILE:=infra/parameters.dev.json}"
: "${ENVIRONMENT:=dev}"
: "${PROJECT:=banking}"
: "${OWNER:=platform-team}"

BICEP_FILE="infra/main.bicep"
DEPLOYMENT_NAME="base-infra-$(date +%s)"

log() { echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] $*"; }

# ---------------------------------------------------------------------------
# Preconditions
# ---------------------------------------------------------------------------
command -v az >/dev/null 2>&1 || { log "ERROR: Azure CLI (az) is not installed."; exit 127; }

log "Validating Bicep template..."
az bicep build --file "${BICEP_FILE}" >/dev/null

# ---------------------------------------------------------------------------
# Resource Group
# ---------------------------------------------------------------------------
log "Ensuring resource group '${AZURE_RESOURCE_GROUP}' exists in '${AZURE_LOCATION}'..."
az group create \
  --name "${AZURE_RESOURCE_GROUP}" \
  --location "${AZURE_LOCATION}" \
  --tags \
    "environment=${ENVIRONMENT}" \
    "project=${PROJECT}" \
    "owner=${OWNER}" \
  --output none

# ---------------------------------------------------------------------------
# What-If preview
# ---------------------------------------------------------------------------
log "Running what-if analysis..."
az deployment group what-if \
  --resource-group "${AZURE_RESOURCE_GROUP}" \
  --name "${DEPLOYMENT_NAME}" \
  --template-file "${BICEP_FILE}" \
  --parameters @"${BICEP_PARAMS_FILE}" \
  --no-pretty-print 2>&1 | grep -v "^$" || true

# ---------------------------------------------------------------------------
# Deploy
# ---------------------------------------------------------------------------
log "Deploying base infrastructure to '${AZURE_RESOURCE_GROUP}'..."
DEPLOY_OUTPUT="$(az deployment group create \
  --resource-group "${AZURE_RESOURCE_GROUP}" \
  --name "${DEPLOYMENT_NAME}" \
  --template-file "${BICEP_FILE}" \
  --parameters @"${BICEP_PARAMS_FILE}" \
  --output json)"

# ---------------------------------------------------------------------------
# Print resource endpoints
# ---------------------------------------------------------------------------
log "Deployment complete. Resource endpoints:"

ACR_LOGIN_SERVER="$(echo "${DEPLOY_OUTPUT}" | python3 -c "import sys,json; print(json.load(sys.stdin)['properties']['outputs']['acrLoginServer']['value'])")"
KV_URI="$(echo "${DEPLOY_OUTPUT}"           | python3 -c "import sys,json; print(json.load(sys.stdin)['properties']['outputs']['keyVaultUri']['value'])")"
APPI_CONN="$(echo "${DEPLOY_OUTPUT}"        | python3 -c "import sys,json; print(json.load(sys.stdin)['properties']['outputs']['appInsightsConnectionString']['value'])")"
CAE_DOMAIN="$(echo "${DEPLOY_OUTPUT}"       | python3 -c "import sys,json; print(json.load(sys.stdin)['properties']['outputs']['containerAppsEnvDomain']['value'])")"
MI_CLIENT_ID="$(echo "${DEPLOY_OUTPUT}"     | python3 -c "import sys,json; print(json.load(sys.stdin)['properties']['outputs']['managedIdentityClientId']['value'])")"

echo ""
echo "  ACR login server          : ${ACR_LOGIN_SERVER}"
echo "  Key Vault URI             : ${KV_URI}"
echo "  App Insights conn string  : ${APPI_CONN}"
echo "  Container Apps env domain : ${CAE_DOMAIN}"
echo "  Managed Identity clientId : ${MI_CLIENT_ID}"
echo ""

log "Verifying ACR login (docker login)..."
az acr login --name "${ACR_LOGIN_SERVER%%.*}" 2>&1 && log "ACR login succeeded." || log "WARN: ACR login failed (check local Docker daemon)."
