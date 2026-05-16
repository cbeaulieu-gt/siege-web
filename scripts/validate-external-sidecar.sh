#!/usr/bin/env bash
# validate-external-sidecar.sh — validate externalBotApiUrl in a Bicep param file
#
# Usage:
#   validate-external-sidecar.sh <param-file>
#
# Exits 0 when externalBotApiUrl is present and starts with https://.
# Exits 1 when absent, empty, or not https://.
# Emits ::error:: prefixed messages on failure so GitHub Actions surfaces them
# in the run UI.
#
# This script is the single source of truth for the validation logic that was
# previously duplicated across deploy-dev and deploy-prod in infra-deploy.yml.
# It is invoked by .github/actions/validate-external-sidecar/action.yml.
# See: issue #435, parent #429.

set -euo pipefail

PARAM_FILE="${1:?Usage: validate-external-sidecar.sh <param-file>}"

# Extract the externalBotApiUrl value, stripping leading/trailing
# whitespace and surrounding quotes (single or double — Bicep only
# accepts single, but the validator is lenient by design so a typo
# produces a clear error rather than a regex miss).
PARAM_VALUE=$(grep -E "^[[:space:]]*param[[:space:]]+externalBotApiUrl[[:space:]]*=" "$PARAM_FILE" \
  | sed -E "s/^[[:space:]]*param[[:space:]]+externalBotApiUrl[[:space:]]*=[[:space:]]*['\"]?([^'\"[:space:]]*)['\"]?[[:space:]]*$/\1/" \
  || true)

if [ -z "$PARAM_VALUE" ]; then
  echo "::error::useExternalSidecar=true but externalBotApiUrl is not set in $PARAM_FILE"
  echo "::error::Add: param externalBotApiUrl = 'https://your-sidecar.example.com'"
  exit 1
fi

if ! [[ "$PARAM_VALUE" =~ ^https:// ]]; then
  echo "::error::externalBotApiUrl in $PARAM_FILE must start with https:// (got: $PARAM_VALUE)"
  echo "::error::Bearer-token traffic must not flow over plaintext http"
  exit 1
fi
