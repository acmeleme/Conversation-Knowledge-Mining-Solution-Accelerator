import base64
import json

from auth.auth_utils import (
    can_access_billing,
    get_authenticated_user_details,
    get_tenantid,
    get_user_roles,
    user_has_role,
)


def _build_headers(*roles: str, extra_claims: list[dict[str, str]] | None = None) -> dict[str, str]:
    claims = [{"typ": "roles", "val": role} for role in roles]
    if extra_claims:
        claims.extend(extra_claims)

    principal = {
        "auth_typ": "aad",
        "claims": claims,
        "name_typ": "name",
        "role_typ": "roles",
    }
    encoded = base64.b64encode(json.dumps(principal).encode("utf-8")).decode("utf-8")
    return {"x-ms-client-principal": encoded}



def test_get_authenticated_user_details_uses_sample_user_in_dev_mode():
    result = get_authenticated_user_details({})

    assert result["user_principal_id"] == "00000000-0000-0000-0000-000000000000"
    assert result["user_name"] == "testusername@constoso.com"
    assert result["auth_provider"] == "aad"



def test_get_authenticated_user_details_reads_easyauth_headers_in_prod_mode():
    result = get_authenticated_user_details(
        {
            "x-ms-client-principal-id": "123",
            "x-ms-client-principal-name": "testuser",
            "x-ms-client-principal-idp": "aad",
            "x-ms-token-aad-id-token": "token123",
            "x-ms-client-principal": "encodedstring",
        }
    )

    assert result == {
        "user_principal_id": "123",
        "user_name": "testuser",
        "auth_provider": "aad",
        "auth_token": "token123",
        "client_principal_b64": "encodedstring",
        "aad_id_token": "token123",
    }



def test_get_user_roles_extracts_all_role_claims():
    headers = _build_headers(
        "callcenter",
        "faturamento",
        extra_claims=[{"typ": "name", "val": "John Doe"}],
    )

    assert get_user_roles(headers) == ["callcenter", "faturamento"]



def test_get_user_roles_defaults_to_callcenter_when_header_is_missing():
    assert get_user_roles({}) == ["callcenter"]



def test_user_has_role_is_case_insensitive():
    assert user_has_role(_build_headers("Faturamento"), "faturamento") is True



def test_can_access_billing_requires_faturamento_role():
    assert can_access_billing(_build_headers("faturamento")) is True
    assert can_access_billing(_build_headers("callcenter")) is False



def test_get_tenantid_reads_tenant_claim_when_top_level_tid_is_missing():
    headers = _build_headers("callcenter", extra_claims=[{"typ": "tid", "val": "tenant-123"}])

    assert get_tenantid(headers["x-ms-client-principal"]) == "tenant-123"



def test_get_tenantid_returns_empty_string_for_invalid_payload():
    assert get_tenantid("notbase64!!!") == ""
