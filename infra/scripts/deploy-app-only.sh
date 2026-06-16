#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <resource-group>"
  exit 1
fi

RESOURCE_GROUP="$1"
IMAGE_TAG="${IMAGE_TAG:-app-only-$(date +%Y%m%d%H%M%S)}"

echo "Deploying application only to resource group: ${RESOURCE_GROUP}"

if [ -z "${APP_NAME:-}" ]; then
  APP_NAME="$(az webapp list --resource-group "$RESOURCE_GROUP" --query "[?starts_with(name, 'app-')].name | [0]" -o tsv)"
fi
if [ -z "${API_NAME:-}" ]; then
  API_NAME="$(az webapp list --resource-group "$RESOURCE_GROUP" --query "[?starts_with(name, 'api-')].name | [0]" -o tsv)"
fi

if [ -z "$APP_NAME" ] || [ -z "$API_NAME" ]; then
  echo "ERROR: Could not discover app/api App Services in resource group '${RESOURCE_GROUP}'."
  exit 1
fi

APP_FX=""
API_FX=""
if [ -z "${APP_REPO:-}" ] || [ -z "${API_REPO:-}" ] || [ -z "${ACR_LOGIN_SERVER:-}" ]; then
  APP_FX="$(az webapp config container show --resource-group "$RESOURCE_GROUP" --name "$APP_NAME" --query "[?name=='DOCKER_CUSTOM_IMAGE_NAME'].value | [0]" -o tsv 2>/dev/null || true)"
  API_FX="$(az webapp config container show --resource-group "$RESOURCE_GROUP" --name "$API_NAME" --query "[?name=='DOCKER_CUSTOM_IMAGE_NAME'].value | [0]" -o tsv 2>/dev/null || true)"
fi

APP_IMAGE_REF="${APP_FX#DOCKER|}"
API_IMAGE_REF="${API_FX#DOCKER|}"

APP_REPO="${APP_REPO:-}"
API_REPO="${API_REPO:-}"
if [[ "$APP_IMAGE_REF" == *"/"* ]]; then
  APP_REPO_WITH_TAG="${APP_IMAGE_REF#*/}"
  APP_REPO="${APP_REPO_WITH_TAG%%:*}"
fi
if [[ "$API_IMAGE_REF" == *"/"* ]]; then
  API_REPO_WITH_TAG="${API_IMAGE_REF#*/}"
  API_REPO="${API_REPO_WITH_TAG%%:*}"
fi

if [ -z "${ACR_LOGIN_SERVER:-}" ]; then
  ACR_LOGIN_SERVER="$(az acr list --resource-group "$RESOURCE_GROUP" --query "[0].loginServer" -o tsv)"
fi
if [ -z "$ACR_LOGIN_SERVER" ]; then
  if [ -n "${AZURE_CONTAINER_REGISTRY_ENDPOINT:-}" ]; then
    ACR_LOGIN_SERVER="$AZURE_CONTAINER_REGISTRY_ENDPOINT"
  else
    AZD_ACR_ENDPOINT="$(azd env get-value AZURE_CONTAINER_REGISTRY_ENDPOINT 2>/dev/null || true)"
    if [ -n "$AZD_ACR_ENDPOINT" ]; then
      ACR_LOGIN_SERVER="$AZD_ACR_ENDPOINT"
    fi
  fi
fi

if [ -z "$ACR_LOGIN_SERVER" ]; then
  AZD_ACR_NAME="$(azd env get-value ACR_NAME 2>/dev/null || true)"
  if [ -n "$AZD_ACR_NAME" ]; then
    ACR_LOGIN_SERVER="${AZD_ACR_NAME}.azurecr.io"
  fi
fi

if [ -z "$ACR_LOGIN_SERVER" ]; then
  ACR_LOGIN_SERVER="$(az acr list --query "[0].loginServer" -o tsv)"
fi

if [ -z "$ACR_LOGIN_SERVER" ] && [[ "$APP_IMAGE_REF" == *"/"* ]]; then
  ACR_LOGIN_SERVER="${APP_IMAGE_REF%%/*}"
fi

if [ -z "$ACR_LOGIN_SERVER" ]; then
  echo "ERROR: Could not resolve ACR endpoint. Set AZURE_CONTAINER_REGISTRY_ENDPOINT or azd env ACR values."
  exit 1
fi

ACR_NAME="${ACR_LOGIN_SERVER%%.*}"

if [ -z "$APP_REPO" ]; then
  APP_REPO="$APP_NAME"
fi
if [ -z "$API_REPO" ]; then
  API_REPO="$API_NAME"
fi

APP_IMAGE="${ACR_LOGIN_SERVER}/${APP_REPO}:${IMAGE_TAG}"
API_IMAGE="${ACR_LOGIN_SERVER}/${API_REPO}:${IMAGE_TAG}"

echo "Using ACR: ${ACR_LOGIN_SERVER}"
echo "Web app: ${APP_NAME}"
echo "API app: ${API_NAME}"
echo "Image tag: ${IMAGE_TAG}"

az acr login --name "$ACR_NAME"

echo "Building and pushing frontend image..."
docker build --platform linux/amd64 --build-arg REACT_APP_VERSION="${IMAGE_TAG}" -f src/App/WebApp.Dockerfile -t "$APP_IMAGE" src/App
docker push "$APP_IMAGE"

echo "Building and pushing API image..."
docker build --platform linux/amd64 --build-arg APP_VERSION="${IMAGE_TAG}" -f src/api/ApiApp.Dockerfile -t "$API_IMAGE" src/api
docker push "$API_IMAGE"

echo "Updating App Service container configuration..."
az webapp config container set \
  --resource-group "$RESOURCE_GROUP" \
  --name "$APP_NAME" \
  --container-image-name "$APP_IMAGE" \
  --container-registry-url "https://${ACR_LOGIN_SERVER}" >/dev/null

az webapp config container set \
  --resource-group "$RESOURCE_GROUP" \
  --name "$API_NAME" \
  --container-image-name "$API_IMAGE" \
  --container-registry-url "https://${ACR_LOGIN_SERVER}" >/dev/null

# Persist the image version as an App Service env var so /api/version can read it
az webapp config appsettings set \
  --resource-group "$RESOURCE_GROUP" \
  --name "$API_NAME" \
  --settings APP_VERSION="${IMAGE_TAG}" >/dev/null

echo "Restarting App Services..."
az webapp restart --resource-group "$RESOURCE_GROUP" --name "$APP_NAME" >/dev/null
az webapp restart --resource-group "$RESOURCE_GROUP" --name "$API_NAME" >/dev/null

# Update Easy Auth on the frontend App Service to use AAD v2.0 tokens and request the
# 'email' scope. This ensures the email claim appears in /.auth/me user_claims so the
# React app can read it directly without needing the backend /api/me fallback.
# Effect is immediate — existing sessions will be revalidated on next request.
echo "Configuring Easy Auth email scope on ${APP_NAME}..."
TENANT_ID="$(az account show --query tenantId -o tsv 2>/dev/null || true)"
if [ -n "$TENANT_ID" ]; then
  az webapp auth microsoft update \
    --resource-group "$RESOURCE_GROUP" \
    --name "$APP_NAME" \
    --issuer "https://login.microsoftonline.com/${TENANT_ID}/v2.0" \
    --login-parameters "scope=openid profile email" \
    --output none 2>/dev/null || \
    echo "WARN: Could not update Easy Auth scope (non-fatal — /api/me fallback is active)"

  AUTH_V2_URL="https://management.azure.com/subscriptions/$(az account show --query id -o tsv)/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.Web/sites/${APP_NAME}/config/authsettingsV2?api-version=2022-03-01"
  AUTH_V2_JSON="$(az rest --method GET --url "$AUTH_V2_URL" --output json)"
  AUTH_V2_PATCHED="$(AUTH_V2_JSON="$AUTH_V2_JSON" python -c 'import json, os; data = json.loads(os.environ["AUTH_V2_JSON"]); data.setdefault("properties", {}); data["properties"].setdefault("platform", {}); data["properties"]["platform"]["enabled"] = True; print(json.dumps(data))')"
  AUTH_V2_FILE="${RESOURCE_GROUP}-${APP_NAME}-authsettingsV2.json"
  printf '%s' "$AUTH_V2_PATCHED" > "$AUTH_V2_FILE"
  az rest --method PUT --url "$AUTH_V2_URL" --headers "Content-Type=application/json" --body @"$AUTH_V2_FILE" --output none >/dev/null
  rm -f "$AUTH_V2_FILE"

  CLIENT_ID=$(AUTH_V2_JSON="$AUTH_V2_JSON" python3 - <<'PY'
import json
import os

data = json.loads(os.environ["AUTH_V2_JSON"])
print(data["properties"]["identityProviders"]["azureActiveDirectory"]["registration"]["clientId"])
PY
  )

  if [ -z "$CLIENT_ID" ]; then
    echo "WARN: Could not resolve Easy Auth client ID; skipping app registration patch."
  else
    APP_REG_OBJECT_ID=$(az ad app show --id "$CLIENT_ID" --query id -o tsv)
    IMP_GRANT_PATCH=$(cat <<'JSON'
{"web":{"implicitGrantSettings":{"enableIdTokenIssuance":true,"enableAccessTokenIssuance":false}}}
JSON
)
    az rest --method PATCH --url "https://graph.microsoft.com/v1.0/applications/${APP_REG_OBJECT_ID}" --headers "Content-Type=application/json" --body "$IMP_GRANT_PATCH" --output none >/dev/null
  fi
else
  echo "WARN: Could not determine tenant ID — skipping Easy Auth scope update"
fi

echo "Application-only deployment completed."
echo "Frontend URL: https://${APP_NAME}.azurewebsites.net"
echo "API URL: https://${API_NAME}.azurewebsites.net"