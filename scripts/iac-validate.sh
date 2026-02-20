#!/usr/bin/env bash
set -Eeuo pipefail

# -----------------------------
# Configuration (override via env)
# -----------------------------
: "${AZURE_LOCATION:=westus2}"
: "${IAC_PREFIX:=copilot-iac}"
: "${IAC_TTL_HOURS:=6}"

# GitHub Actions Environment name (should be set by workflow env; default to dev)
: "${GH_ACTIONS_ENVIRONMENT:=dev}"

# Bicep defaults (override if your repo differs)
: "${BICEP_FILE:=infra/main.bicep}"
: "${BICEP_PARAMS_FILE:=infra/parameters.json}"

# azd behavior
: "${AZD_ENV_NAME:=}"                     # will default to GH_ACTIONS_ENVIRONMENT (dev)
: "${AZD_USE_RG_SCOPED_DEPLOYMENTS:=true}"

# -----------------------------
# Helpers
# -----------------------------
log() { echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] $*"; }

retry() {
  # retry <max_attempts> <sleep_seconds> <command...>
  local -r max_attempts="$1"; shift
  local -r sleep_seconds="$1"; shift
  local attempt=1
  until "$@"; do
    if (( attempt >= max_attempts )); then
      log "ERROR: command failed after ${attempt} attempts: $*"
      return 1
    fi
    log "WARN: command failed (attempt ${attempt}/${max_attempts}). Retrying in ${sleep_seconds}s: $*"
    sleep "${sleep_seconds}"
    attempt=$((attempt + 1))
  done
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { log "ERROR: missing required command: $1"; exit 127; }
}

# -----------------------------
# Preconditions
# -----------------------------
require_cmd az

IS_AZD_PROJECT=false
if [[ -f "azure.yaml" ]]; then
  IS_AZD_PROJECT=true
  require_cmd azd
fi

HAS_BICEP=false
if [[ -f "${BICEP_FILE}" ]]; then
  HAS_BICEP=true
fi

# Derive RG name
if [[ -z "${IAC_RG:-}" ]]; then
  if [[ -n "${GITHUB_RUN_ID:-}" ]]; then
    IAC_RG="${IAC_PREFIX}-${GH_ACTIONS_ENVIRONMENT}-${GITHUB_REPOSITORY##*/}-${GITHUB_RUN_ID}"
  else
    IAC_RG="${IAC_PREFIX}-${GH_ACTIONS_ENVIRONMENT}-local-$(date +%s)"
  fi
fi

DEPLOYMENT_NAME="iac-validate-$(date +%s)"
CREATED_RG=false

cleanup() {
  local exit_code=$?
  set +e

  log "Cleanup starting (exit_code=${exit_code})..."

  # If azd was used, attempt azd down first (best effort).
  if [[ "${IS_AZD_PROJECT}" == "true" && -n "${AZD_ENV_NAME:-}" ]]; then
    log "Attempting azd down for environment: ${AZD_ENV_NAME}"
    # azd down is standard; commonly used with --purge --force for cleanup. [11](https://www.youtube.com/watch?v=zm-BBZIAJ0c)[12](https://code.claude.com/docs/en/overview)[13](https://deepwiki.com/anthropics/claude-code)
    azd env select "${AZD_ENV_NAME}" >/dev/null 2>&1 || true
    azd down --purge --force >/dev/null 2>&1 || true
  fi

  # Always ensure the RG is deleted (safety net).
  if [[ "${CREATED_RG}" == "true" ]]; then
    log "Deleting resource group (safety net): ${IAC_RG}"
    az group delete --name "${IAC_RG}" --yes --no-wait >/dev/null 2>&1 || true
  fi

  log "Cleanup completed."
  exit "${exit_code}"
}
trap cleanup EXIT

# -----------------------------
# Create Resource Group (ephemeral)
# -----------------------------
log "Creating ephemeral resource group: ${IAC_RG} in ${AZURE_LOCATION}"
retry 3 5 az group create \
  --name "${IAC_RG}" \
  --location "${AZURE_LOCATION}" \
  --tags \
    "managedBy=copilot-iac" \
    "environment=${GH_ACTIONS_ENVIRONMENT}" \
    "ttlHours=${IAC_TTL_HOURS}" \
    "repo=${GITHUB_REPOSITORY:-local}" \
    "runId=${GITHUB_RUN_ID:-local}" \
  >/dev/null
CREATED_RG=true

# -----------------------------
# AZD Provision (if applicable)
# -----------------------------
if [[ "${IS_AZD_PROJECT}" == "true" ]]; then
  # Default AZD environment name to GH Actions Environment ("dev") unless overridden.
  if [[ -z "${AZD_ENV_NAME}" ]]; then
    AZD_ENV_NAME="${GH_ACTIONS_ENVIRONMENT}"
    # Make it unique per run when in CI
    if [[ -n "${GITHUB_RUN_ID:-}" ]]; then
      AZD_ENV_NAME="${GH_ACTIONS_ENVIRONMENT}-${GITHUB_RUN_ID}"
    fi
  fi

  log "AZD project detected. Using AZD environment: ${AZD_ENV_NAME}"

  # azd uses environment variables stored per environment. [9](https://code.visualstudio.com/docs/copilot/copilot-coding-agent)[10](https://bing.com/search?q=VS+Code+GitHub+Copilot+agent+mode+documentation)
  azd env new "${AZD_ENV_NAME}" --no-prompt >/dev/null 2>&1 || azd env select "${AZD_ENV_NAME}" >/dev/null

  azd env set AZURE_LOCATION "${AZURE_LOCATION}" >/dev/null
  azd env set AZURE_SUBSCRIPTION_ID "$(az account show --query id -o tsv)" >/dev/null

  # Set AZURE_RESOURCE_GROUP to deploy to this pre-created ephemeral RG when supported. 
  azd env set AZURE_RESOURCE_GROUP "${IAC_RG}" >/dev/null

  if [[ "${AZD_USE_RG_SCOPED_DEPLOYMENTS}" == "true" ]]; then
    log "Enabling azd resource group scoped deployments (beta). "
    azd config set alpha.resourceGroupDeployments on >/dev/null 2>&1 || true
  fi

  log "Running: azd provision (non-interactive)"
  # azd provision provisions Azure resources. [14](https://www.anthropic.com/engineering/advanced-tool-use)[11](https://www.youtube.com/watch?v=zm-BBZIAJ0c)
  retry 2 10 azd provision --no-prompt
fi

# -----------------------------
# Bicep Validate + Deploy (if present)
# -----------------------------
if [[ "${HAS_BICEP}" == "true" ]]; then
  log "Bicep detected at ${BICEP_FILE}. Building for compilation validation..."
  retry 2 5 az bicep build --file "${BICEP_FILE}" >/dev/null

  log "Validating Bicep deployment (ARM validate) into RG: ${IAC_RG}"
  if [[ -f "${BICEP_PARAMS_FILE}" ]]; then
    retry 2 5 az deployment group validate \
      --resource-group "${IAC_RG}" \
      --name "${DEPLOYMENT_NAME}" \
      --template-file "${BICEP_FILE}" \
      --parameters @"${BICEP_PARAMS_FILE}" \
      >/dev/null
  else
    retry 2 5 az deployment group validate \
      --resource-group "${IAC_RG}" \
      --name "${DEPLOYMENT_NAME}" \
      --template-file "${BICEP_FILE}" \
      >/dev/null
  fi

  log "Deploying Bicep (create) into RG: ${IAC_RG}"
  if [[ -f "${BICEP_PARAMS_FILE}" ]]; then
    retry 2 10 az deployment group create \
      --resource-group "${IAC_RG}" \
      --name "${DEPLOYMENT_NAME}" \
      --template-file "${BICEP_FILE}" \
      --parameters @"${BICEP_PARAMS_FILE}"
  else
    retry 2 10 az deployment group create \
      --resource-group "${IAC_RG}" \
      --name "${DEPLOYMENT_NAME}" \
      --template-file "${BICEP_FILE}"
  fi
fi

# -----------------------------
# Post-deploy smoke validation (customize)
# -----------------------------
log "Running post-deploy smoke checks..."
retry 2 5 az group show --name "${IAC_RG}" >/dev/null

RESOURCE_COUNT="$(az resource list --resource-group "${IAC_RG}" --query "length(@)" -o tsv || echo 0)"
log "Resources in ${IAC_RG}: ${RESOURCE_COUNT}"
if [[ "${RESOURCE_COUNT}" -lt 1 ]]; then
  log "ERROR: No resources found in RG after deployment. Failing."
  exit 1
fi

log "IaC validation succeeded."