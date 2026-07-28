from pydantic import BaseModel
from typing import List, Optional


class UserInfo(BaseModel):
    user_name: str | None
    user_principal_id: str | None
    roles: List[str]
    can_access_billing: bool
    allowed_topics: Optional[List[str]] = None
    tenant_id: Optional[str] = None
    memory_scope: Optional[str] = None
