from __future__ import annotations

import base64
import json
import logging
from collections.abc import Mapping
from typing import Any

logger = logging.getLogger(__name__)

CLIENT_PRINCIPAL_HEADER = "x-ms-client-principal"
ROLE_CLAIM_TYPE = "roles"
DEFAULT_DEV_ROLE = "callcenter"
BILLING_ROLE = "faturamento"
TENANT_ID_CLAIM_TYPES = {
    "tid",
    "http://schemas.microsoft.com/identity/claims/tenantid",
}


def _normalize_headers(request_headers: Mapping[str, str] | None) -> dict[str, str]:
    """Return request headers with lower-cased keys for case-insensitive lookups."""
    if not request_headers:
        return {}

    return {str(key).lower(): value for key, value in request_headers.items()}


def _decode_client_principal(client_principal_b64: str | None) -> dict[str, Any]:
    """Decode the EasyAuth client principal payload into a dictionary."""
    if not client_principal_b64:
        return {}

    try:
        padded_value = client_principal_b64 + ("=" * (-len(client_principal_b64) % 4))
        decoded_bytes = base64.b64decode(padded_value)
        return json.loads(decoded_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.warning("Unable to decode x-ms-client-principal header: %s", exc)
        return {}


def _extract_claims(client_principal_b64: str | None) -> list[dict[str, Any]]:
    """Extract the claim collection from an EasyAuth client principal payload."""
    client_principal = _decode_client_principal(client_principal_b64)
    claims = client_principal.get("claims", [])
    if isinstance(claims, list):
        return [claim for claim in claims if isinstance(claim, dict)]

    return []


def get_authenticated_user_details(request_headers: Mapping[str, str]) -> dict[str, str | None]:
    """Return the normalized user details exposed by Azure App Service EasyAuth."""
    normalized_headers = _normalize_headers(request_headers)

    if "x-ms-client-principal-id" not in normalized_headers:
        # In local development EasyAuth headers are not present, so use the sample payload.
        from . import sample_user

        raw_user_object = _normalize_headers(sample_user.sample_user)
    else:
        raw_user_object = normalized_headers

    return {
        "user_principal_id": raw_user_object.get("x-ms-client-principal-id"),
        "user_name": raw_user_object.get("x-ms-client-principal-name"),
        "auth_provider": raw_user_object.get("x-ms-client-principal-idp"),
        "auth_token": raw_user_object.get("x-ms-token-aad-id-token"),
        "client_principal_b64": raw_user_object.get(CLIENT_PRINCIPAL_HEADER),
        "aad_id_token": raw_user_object.get("x-ms-token-aad-id-token"),
    }


def get_tenantid(client_principal_b64: str | None) -> str:
    """Extract the tenant ID from the EasyAuth client principal payload when present."""
    client_principal = _decode_client_principal(client_principal_b64)
    tenant_id = client_principal.get("tid")
    if isinstance(tenant_id, str):
        return tenant_id

    for claim in _extract_claims(client_principal_b64):
        claim_type = claim.get("typ")
        claim_value = claim.get("val")
        if claim_type in TENANT_ID_CLAIM_TYPES and isinstance(claim_value, str):
            return claim_value

    return ""


def get_user_roles(request_headers: Mapping[str, str]) -> list[str]:
    """Extract app roles from the EasyAuth x-ms-client-principal claims payload."""
    normalized_headers = _normalize_headers(request_headers)
    client_principal_b64 = normalized_headers.get(CLIENT_PRINCIPAL_HEADER)

    if not client_principal_b64:
        logger.info(
            "x-ms-client-principal header not present; defaulting to %s role for development.",
            DEFAULT_DEV_ROLE,
        )
        return [DEFAULT_DEV_ROLE]

    roles: list[str] = []
    for claim in _extract_claims(client_principal_b64):
        claim_type = str(claim.get("typ") or "").casefold()
        claim_value = claim.get("val")
        if claim_type == ROLE_CLAIM_TYPE and isinstance(claim_value, str) and claim_value not in roles:
            roles.append(claim_value)

    return roles


def user_has_role(request_headers: Mapping[str, str], role: str) -> bool:
    """Return True when the current user has the requested app role."""
    requested_role = role.casefold()
    return any(user_role.casefold() == requested_role for user_role in get_user_roles(request_headers))


def can_access_billing(roles_or_headers) -> bool:
    """Return True when the effective roles include the faturamento role."""
    if isinstance(roles_or_headers, Mapping):
        roles = get_user_roles(roles_or_headers)
    else:
        roles = roles_or_headers or []

    return any(str(role).casefold() == BILLING_ROLE for role in roles)