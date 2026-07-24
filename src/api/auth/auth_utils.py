from __future__ import annotations

import base64
from contextvars import ContextVar, Token
import json
import logging
from collections.abc import Mapping
from typing import Any

logger = logging.getLogger(__name__)

CLIENT_PRINCIPAL_HEADER = "x-ms-client-principal"
ROLE_CLAIM_TYPE = "roles"
DEFAULT_DEV_ROLE = "callcenter"
BILLING_ROLE = "faturamento"
OPERADOR_OUTROS_ROLE = "operador-outros"
# Backward-compatible alias for legacy checks/tests.
OPERADOR_ROLE = OPERADOR_OUTROS_ROLE
OPERADOR_CARTAO_ROLE = "operador-cartao"
# Backward-compatible alias kept for legacy imports; the effective role is operador-cartao.
FINANCEIRO_ROLE = OPERADOR_CARTAO_ROLE
TENANT_ID_CLAIM_TYPES = {
    "tid",
    "http://schemas.microsoft.com/identity/claims/tenantid",
}
UPN_CLAIM_TYPES = {
    "preferred_username",
    "upn",
    "name",
    "email",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/upn",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
}


def _normalize_headers(request_headers: Mapping[str, str] | None) -> dict[str, str]:
    """Return request headers with lower-cased keys for case-insensitive lookups."""
    if not request_headers:
        return {}

    return {str(key).lower(): value for key, value in request_headers.items()}


def _normalize_identity(value: str | None) -> str:
    """Normalize identity strings for deterministic matching."""
    if not isinstance(value, str):
        return ""
    return value.strip().casefold()


def _extract_local_part(identity: str | None) -> str:
    """Extract the local-part (before @) from a normalized identity."""
    normalized_identity = _normalize_identity(identity)
    if not normalized_identity:
        return ""
    local_part, separator, _ = normalized_identity.partition("@")
    return local_part if separator else normalized_identity


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


def _extract_upn_from_client_principal(client_principal_b64: str | None) -> str:
    """Extract user principal name from EasyAuth client principal payload."""
    client_principal = _decode_client_principal(client_principal_b64)

    direct_upn = client_principal.get("userDetails") or client_principal.get("userdetails")
    normalized_direct_upn = _normalize_identity(direct_upn if isinstance(direct_upn, str) else None)
    if "@" in normalized_direct_upn:
        return normalized_direct_upn

    for claim in _extract_claims(client_principal_b64):
        claim_type = _normalize_identity(str(claim.get("typ") or ""))
        claim_value = claim.get("val")
        normalized_claim_value = _normalize_identity(claim_value if isinstance(claim_value, str) else None)
        if claim_type in UPN_CLAIM_TYPES and "@" in normalized_claim_value:
            return normalized_claim_value

    return ""


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


DEMO_ROLE_HEADER = "x-demo-role"
ALLOWED_DEMO_ROLES = {
    OPERADOR_OUTROS_ROLE,
    OPERADOR_CARTAO_ROLE,
    BILLING_ROLE,
    DEFAULT_DEV_ROLE,
}

# Mapeamento de UPN (email Entra ID) → papéis RBAC
UPN_ROLE_MAP: dict[str, list[str]] = {
    "operador-callcenter@mngenvmcap197214.onmicrosoft.com": [OPERADOR_OUTROS_ROLE],
    "financeiro-faturamento@mngenvmcap197214.onmicrosoft.com": [OPERADOR_CARTAO_ROLE, BILLING_ROLE],
    "operador-cartao@mngenvmcap299208.onmicrosoft.com": [OPERADOR_CARTAO_ROLE],
    "operador-outros@mngenvmcap299208.onmicrosoft.com": [OPERADOR_OUTROS_ROLE],
}
UPN_LOCALPART_ROLE_MAP: dict[str, list[str]] = {
    "operador-callcenter": [OPERADOR_OUTROS_ROLE],
    "financeiro-faturamento": [OPERADOR_CARTAO_ROLE, BILLING_ROLE],
    "operador-cartao": [OPERADOR_CARTAO_ROLE],
    "operador-outros": [OPERADOR_OUTROS_ROLE],
}

RESTRICTED_TOPICS_BY_ROLE: dict[str, list[str]] = {
    OPERADOR_OUTROS_ROLE: [
        "Cartao de Credito — Fatura e Pagamento",
        "Cartao de Credito — Bloqueio e Contestacao",
        "Cartao de Credito",
    ],
}

_REQUEST_ROLES_CONTEXT: ContextVar[tuple[str, ...]] = ContextVar(
    "request_roles_context",
    default=(),
)


LEGACY_ROLE_NORMALIZATION = {
    "operador": OPERADOR_OUTROS_ROLE,
}


def _normalize_role_name(role: str) -> str:
    normalized_role = role.casefold().strip()
    return LEGACY_ROLE_NORMALIZATION.get(normalized_role, normalized_role)


def get_restricted_topics(role: str) -> list[str]:
    """Retorna lista de tópicos restritos para o role do usuário."""
    normalized_role = _normalize_role_name(role)
    return list(RESTRICTED_TOPICS_BY_ROLE.get(normalized_role, []))


def get_roles_restricted_topics(roles: list[str] | tuple[str, ...] | None) -> list[str]:
    """Retorna a união dos tópicos restritos aplicáveis aos roles recebidos."""
    restricted_topics: list[str] = []
    for role in roles or []:
        for topic in get_restricted_topics(str(role)):
            if topic not in restricted_topics:
                restricted_topics.append(topic)
    return restricted_topics


def is_topic_restricted(role: str, topic: str) -> bool:
    """Verifica se um tópico é restrito para o role."""
    restricted = get_restricted_topics(role)
    if not restricted or not isinstance(topic, str):
        return False

    topic_lower = topic.casefold().strip()
    return any(
        restricted_topic.casefold() in topic_lower or topic_lower in restricted_topic.casefold()
        for restricted_topic in restricted
    )


def text_contains_restricted_topic(
    roles: list[str] | tuple[str, ...] | None,
    text: str | None,
) -> bool:
    """Retorna True quando o texto menciona qualquer tópico restrito dos roles informados."""
    if not isinstance(text, str) or not text.strip():
        return False

    return any(is_topic_restricted(str(role), text) for role in (roles or []))


def set_request_access_context(roles: list[str] | tuple[str, ...] | None) -> Token:
    """Armazena os roles efetivos do request no contexto assíncrono atual."""
    normalized_roles = tuple(_normalize_role_name(str(role)) for role in (roles or []))
    return _REQUEST_ROLES_CONTEXT.set(normalized_roles)


def reset_request_access_context(token: Token) -> None:
    """Restaura o contexto assíncrono anterior de roles do request."""
    _REQUEST_ROLES_CONTEXT.reset(token)


def get_current_request_roles() -> list[str]:
    """Retorna os roles efetivos armazenados no contexto do request atual."""
    return list(_REQUEST_ROLES_CONTEXT.get())


def get_current_restricted_topics() -> list[str]:
    """Retorna os tópicos restritos dos roles armazenados no contexto atual."""
    return get_roles_restricted_topics(get_current_request_roles())


def get_user_roles(request_headers: Mapping[str, str]) -> list[str]:
    """Extract app roles from EasyAuth claims or X-Demo-Role header (demo mode).

    Priority order:
    1. EasyAuth x-ms-client-principal roles claims
    2. UPN-based mapping via x-ms-client-principal-name (fallback)
    3. x-demo-role header (demo/testing override when EasyAuth identity is absent)
    4. Default development role
    """
    normalized_headers = _normalize_headers(request_headers)
    has_easyauth_identity = any(
        normalized_headers.get(header_name)
        for header_name in (
            "x-ms-client-principal-id",
            "x-ms-client-principal-name",
            CLIENT_PRINCIPAL_HEADER,
        )
    )

    # Demo mode: header x-demo-role allows simulating roles without EasyAuth.
    # In production EasyAuth requests, mapped/claim roles must take precedence.
    demo_role = normalized_headers.get(DEMO_ROLE_HEADER)
    if demo_role and demo_role.casefold() in ALLOWED_DEMO_ROLES and not has_easyauth_identity:
        logger.info("Demo mode: using role '%s' from %s header.", demo_role, DEMO_ROLE_HEADER)
        return [_normalize_role_name(demo_role)]

    client_principal_b64 = normalized_headers.get(CLIENT_PRINCIPAL_HEADER)
    roles: list[str] = []
    if client_principal_b64:
        for claim in _extract_claims(client_principal_b64):
            claim_type = str(claim.get("typ") or "").casefold()
            claim_value = claim.get("val")
            if claim_type != ROLE_CLAIM_TYPE or not isinstance(claim_value, str):
                continue

            normalized_role = _normalize_role_name(claim_value)
            if normalized_role and normalized_role not in roles:
                roles.append(normalized_role)

    if roles:
        return roles

    # EasyAuth: resolve role via UPN mapping (email do Entra ID)
    upn_from_header = _normalize_identity(normalized_headers.get("x-ms-client-principal-name"))
    upn_from_claims = _extract_upn_from_client_principal(client_principal_b64)
    upn = upn_from_header or upn_from_claims
    if upn and upn in UPN_ROLE_MAP:
        mapped_roles = UPN_ROLE_MAP[upn]
        logger.info("EasyAuth UPN '%s' mapped to roles: %s", upn, mapped_roles)
        return list(mapped_roles)
    upn_local_part = _extract_local_part(upn)
    if upn_local_part and upn_local_part in UPN_LOCALPART_ROLE_MAP:
        mapped_roles = UPN_LOCALPART_ROLE_MAP[upn_local_part]
        logger.info(
            "EasyAuth UPN local-part '%s' mapped to roles: %s",
            upn_local_part,
            mapped_roles,
        )
        return list(mapped_roles)

    if not client_principal_b64:
        logger.info(
            "x-ms-client-principal header not present; defaulting to %s role for development.",
            DEFAULT_DEV_ROLE,
        )
        return [DEFAULT_DEV_ROLE]

    if demo_role and demo_role.casefold() in ALLOWED_DEMO_ROLES:
        logger.info(
            "EasyAuth identity found without mapped/claim roles; ignoring %s override '%s'.",
            DEMO_ROLE_HEADER,
            demo_role,
        )

    logger.info("Authenticated user '%s' has no mapped role; defaulting to %s.", upn or "unknown", DEFAULT_DEV_ROLE)
    return [DEFAULT_DEV_ROLE]


def user_has_role(request_headers: Mapping[str, str], role: str) -> bool:
    """Return True when the current user has the requested app role."""
    requested_role = role.casefold()
    return any(user_role.casefold() == requested_role for user_role in get_user_roles(request_headers))


def can_access_billing(roles_or_headers) -> bool:
    """Return True when the effective roles include billing or operador-cartao."""
    if isinstance(roles_or_headers, Mapping):
        roles = get_user_roles(roles_or_headers)
    else:
        roles = roles_or_headers or []

    valid_billing_roles = {BILLING_ROLE, OPERADOR_CARTAO_ROLE}
    return any(str(role).casefold() in valid_billing_roles for role in roles)
