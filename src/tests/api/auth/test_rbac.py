import base64
import json

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from auth.rbac import RESTRICTED_TOPIC, filter_topics_by_role, get_current_user_roles, require_role

app = FastAPI()


@app.get("/roles")
def read_roles(roles: list[str] = Depends(get_current_user_roles)):
    return {"roles": roles}


@app.get("/billing")
def billing_route(_: list[str] = Depends(require_role(["faturamento"]))):
    return {"allowed": True}


client = TestClient(app)



def _headers(*roles: str) -> dict[str, str]:
    principal = {
        "auth_typ": "aad",
        "claims": [{"typ": "roles", "val": role} for role in roles],
        "name_typ": "name",
        "role_typ": "roles",
    }
    encoded = base64.b64encode(json.dumps(principal).encode("utf-8")).decode("utf-8")
    return {"x-ms-client-principal": encoded}



def test_get_current_user_roles_dependency_reads_easyauth_roles():
    response = client.get("/roles", headers=_headers("callcenter", "faturamento"))

    assert response.status_code == 200
    assert response.json() == {"roles": ["callcenter", "faturamento"]}



def test_require_role_allows_authorized_users():
    response = client.get("/billing", headers=_headers("faturamento"))

    assert response.status_code == 200
    assert response.json() == {"allowed": True}



def test_require_role_blocks_unauthorized_users():
    response = client.get("/billing", headers=_headers("callcenter"))

    assert response.status_code == 403
    assert response.json()["detail"] == "You do not have permission to access this resource."



def test_filter_topics_by_role_hides_restricted_topic_for_callcenter():
    topics = ["General Support", RESTRICTED_TOPIC, "Technical Issues"]

    assert filter_topics_by_role(topics, ["callcenter"]) == ["General Support", "Technical Issues"]



def test_filter_topics_by_role_keeps_restricted_topic_for_faturamento():
    topics = ["General Support", RESTRICTED_TOPIC, "Technical Issues"]

    assert filter_topics_by_role(topics, ["faturamento"]) == topics
