#!/usr/bin/env bash
set -euo pipefail

SUBSCRIPTION_ID="a2ec8402-d75b-419c-b71d-7558309c50dc"
RESOURCE_GROUP="rg-callcenter-100"
APP_DISPLAY_NAME="ckm-callcenter-app"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_PATH="${SCRIPT_DIR}/.rbac-output.json"

info() {
  printf '\033[1;36m[INFO]\033[0m %s\n' "$1" >&2
}

success() {
  printf '\033[1;32m[OK]\033[0m %s\n' "$1" >&2
}

warn() {
  printf '\033[1;33m[WARN]\033[0m %s\n' "$1" >&2
}

run_az() {
  local output
  set +e
  output=$(az "$@" 2>&1)
  local status=$?
  set -e
  if [ $status -ne 0 ]; then
    printf 'az %s failed.\n%s\n' "$*" "$output" >&2
    exit $status
  fi
  printf '%s' "$output"
}

new_temp_password() {
  python3 - <<'PY'
import uuid
print(f"Temp!{uuid.uuid4().hex[:12]}Aa1")
PY
}

ensure_python3() {
  if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 é obrigatório para processar JSON neste script." >&2
    exit 1
  fi
}

ensure_user_and_role_assignment() {
  local display_name="$1"
  local upn="$2"
  local role_value="$3"
  local role_id="$4"
  local user_json
  local user_id
  local created="false"
  local temp_password=""

  user_json=$(run_az ad user list --filter "userPrincipalName eq '${upn}'" --query "[0]" --output json)
  user_id=$(python3 - "$user_json" <<'PY'
import json, sys
value = json.loads(sys.argv[1])
print("" if value is None else value.get("id", ""))
PY
)

  if [ -z "$user_id" ]; then
    info "Criando usuário de teste ${upn}"
    temp_password=$(new_temp_password)
    user_json=$(run_az ad user create --display-name "$display_name" --user-principal-name "$upn" --password "$temp_password" --force-change-password-next-sign-in true --output json)
    user_id=$(python3 - "$user_json" <<'PY'
import json, sys
value = json.loads(sys.argv[1])
print(value["id"])
PY
)
    created="true"
  else
    info "Usuário de teste ${upn} já existe."
  fi

  local assignments_json
  local already_assigned
  assignments_json=$(run_az rest --method GET --url "https://graph.microsoft.com/v1.0/users/${user_id}/appRoleAssignments" --output json)
  already_assigned=$(python3 - "$assignments_json" "$SERVICE_PRINCIPAL_OBJECT_ID" "$role_id" <<'PY'
import json, sys
payload = json.loads(sys.argv[1])
service_principal_id = sys.argv[2]
role_id = sys.argv[3]
for item in payload.get("value", []):
    if item.get("resourceId") == service_principal_id and item.get("appRoleId") == role_id:
        print("true")
        break
else:
    print("false")
PY
)

  if [ "$already_assigned" != "true" ]; then
    info "Associando role '${role_value}' ao usuário ${upn}"
    local assignment_body
    assignment_body=$(python3 - "$user_id" "$SERVICE_PRINCIPAL_OBJECT_ID" "$role_id" <<'PY'
import json, sys
print(json.dumps({
    "principalId": sys.argv[1],
    "resourceId": sys.argv[2],
    "appRoleId": sys.argv[3]
}, separators=(",", ":")))
PY
)
    run_az rest --method POST --url "https://graph.microsoft.com/v1.0/users/${user_id}/appRoleAssignments" --headers "Content-Type=application/json" --body "$assignment_body" --output json >/dev/null
  else
    info "Role '${role_value}' já associada a ${upn}"
  fi

  python3 - "$display_name" "$upn" "$user_id" "$role_value" "$created" "$temp_password" <<'PY'
import json, sys
print(json.dumps({
    "displayName": sys.argv[1],
    "userPrincipalName": sys.argv[2],
    "objectId": sys.argv[3],
    "role": sys.argv[4],
    "created": sys.argv[5] == "true",
    "temporaryPassword": sys.argv[6] or None
}, separators=(",", ":")))
PY
}

ensure_python3

info "Definindo contexto da assinatura Azure"
run_az account set --subscription "$SUBSCRIPTION_ID" >/dev/null

TENANT_ID=$(run_az account show --subscription "$SUBSCRIPTION_ID" --query tenantId --output tsv)
DOMAINS_JSON=$(run_az rest --method GET --url "https://graph.microsoft.com/v1.0/domains" --output json)
TENANT_DOMAIN=$(python3 - "$DOMAINS_JSON" <<'PY'
import json, sys
payload = json.loads(sys.argv[1])
domains = payload.get("value", [])
defaults = [d["id"] for d in domains if d.get("isDefault") and d.get("id")]
if defaults:
    print(defaults[0])
else:
    onmicrosoft = [d["id"] for d in domains if d.get("id", "").endswith(".onmicrosoft.com")]
    if not onmicrosoft:
        raise SystemExit("Não foi possível resolver um domínio .onmicrosoft.com")
    print(onmicrosoft[0])
PY
)
success "Tenant resolvido: ${TENANT_DOMAIN}"

APP_ID=$(run_az ad app list --display-name "$APP_DISPLAY_NAME" --query "[0].appId" --output tsv)
if [ -z "$APP_ID" ]; then
  info "Criando App Registration '${APP_DISPLAY_NAME}'"
  APP_JSON=$(run_az ad app create --display-name "$APP_DISPLAY_NAME" --sign-in-audience AzureADMyOrg --output json)
  APP_ID=$(python3 - "$APP_JSON" <<'PY'
import json, sys
print(json.loads(sys.argv[1])["appId"])
PY
)
else
  info "App Registration '${APP_DISPLAY_NAME}' já existe."
  APP_JSON=$(run_az ad app show --id "$APP_ID" --output json)
fi

APP_OBJECT_ID=$(python3 - "$APP_JSON" <<'PY'
import json, sys
print(json.loads(sys.argv[1])["id"])
PY
)

APP_ROLE_PATCH=$(python3 - "$APP_JSON" <<'PY'
import json, sys, uuid
app = json.loads(sys.argv[1])
existing_roles = app.get("appRoles") or []
preserved = [role for role in existing_roles if role.get("value") not in {"callcenter", "faturamento"}]

def build_role(value, display_name, description):
    existing = next((role for role in existing_roles if role.get("value") == value), None)
    role_id = existing.get("id") if existing else str(uuid.uuid4())
    return {
        "allowedMemberTypes": ["User"],
        "description": description,
        "displayName": display_name,
        "id": role_id,
        "isEnabled": True,
        "origin": "Application",
        "value": value,
    }

payload = {
    "appRoles": preserved + [
        build_role("callcenter", "Call Center Operator", "Acesso a todos os tópicos exceto Billing and Payment Issues"),
        build_role("faturamento", "Financeiro/Faturamento", "Acesso completo incluindo Billing and Payment Issues"),
    ]
}
print(json.dumps(payload, separators=(",", ":")))
PY
)

info "Atualizando App Roles da aplicação"
run_az rest --method PATCH --url "https://graph.microsoft.com/v1.0/applications/${APP_OBJECT_ID}" --headers "Content-Type=application/json" --body "$APP_ROLE_PATCH" --output json >/dev/null
APP_JSON=$(run_az ad app show --id "$APP_ID" --output json)
CALLCENTER_ROLE_ID=$(python3 - "$APP_JSON" <<'PY'
import json, sys
for role in json.loads(sys.argv[1]).get("appRoles", []):
    if role.get("value") == "callcenter":
        print(role["id"])
        break
PY
)
FATURAMENTO_ROLE_ID=$(python3 - "$APP_JSON" <<'PY'
import json, sys
for role in json.loads(sys.argv[1]).get("appRoles", []):
    if role.get("value") == "faturamento":
        print(role["id"])
        break
PY
)
success "App Roles configuradas"

SERVICE_PRINCIPAL_OBJECT_ID=$(run_az ad sp list --filter "appId eq '${APP_ID}'" --query "[0].id" --output tsv)
if [ -z "$SERVICE_PRINCIPAL_OBJECT_ID" ]; then
  info "Criando Service Principal"
  SERVICE_PRINCIPAL_JSON=$(run_az ad sp create --id "$APP_ID" --output json)
  SERVICE_PRINCIPAL_OBJECT_ID=$(python3 - "$SERVICE_PRINCIPAL_JSON" <<'PY'
import json, sys
print(json.loads(sys.argv[1])["id"])
PY
)
  sleep 10
else
  info "Service Principal já existe."
fi

OPERATOR_JSON=$(ensure_user_and_role_assignment "Operador Call Center" "operador-callcenter@${TENANT_DOMAIN}" "callcenter" "$CALLCENTER_ROLE_ID")
FINANCE_JSON=$(ensure_user_and_role_assignment "Financeiro Faturamento" "financeiro-faturamento@${TENANT_DOMAIN}" "faturamento" "$FATURAMENTO_ROLE_ID")

python3 - "$OUTPUT_PATH" "$SUBSCRIPTION_ID" "$RESOURCE_GROUP" "$TENANT_ID" "$TENANT_DOMAIN" "$APP_DISPLAY_NAME" "$APP_ID" "$APP_OBJECT_ID" "$SERVICE_PRINCIPAL_OBJECT_ID" "$CALLCENTER_ROLE_ID" "$FATURAMENTO_ROLE_ID" "$OPERATOR_JSON" "$FINANCE_JSON" <<'PY'
import json, sys
payload = {
    "generatedAt": __import__("datetime").datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    "subscriptionId": sys.argv[2],
    "resourceGroupName": sys.argv[3],
    "tenantId": sys.argv[4],
    "tenantDomain": sys.argv[5],
    "appRegistration": {
        "displayName": sys.argv[6],
        "clientId": sys.argv[7],
        "objectId": sys.argv[8],
        "servicePrincipalObjectId": sys.argv[9],
    },
    "appRoles": {
        "callcenter": {
            "id": sys.argv[10],
            "displayName": "Call Center Operator",
            "description": "Acesso a todos os tópicos exceto Billing and Payment Issues",
        },
        "faturamento": {
            "id": sys.argv[11],
            "displayName": "Financeiro/Faturamento",
            "description": "Acesso completo incluindo Billing and Payment Issues",
        },
    },
    "testUsers": [json.loads(sys.argv[12]), json.loads(sys.argv[13])],
}
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(payload, handle, ensure_ascii=False, indent=2)
PY
success "Arquivo de saída gerado em ${OUTPUT_PATH}"

printf '\n=== Próximos passos: Easy Auth no App Service ===\n'
printf '1. Execute: ./configure-easy-auth.ps1 -ClientId %s -TenantId %s\n' "$APP_ID" "$TENANT_ID"
printf '2. Verifique os redirect URIs para https://<app>.azurewebsites.net/.auth/login/aad/callback\n'
printf '3. Em App Service Authentication, confirme Redirect to identity provider e Token Store habilitados.\n'
printf '4. Valide a claim roles no token JWT dos usuários de teste.\n\n'
success "Client ID: ${APP_ID}"
success "Tenant ID: ${TENANT_ID}"
