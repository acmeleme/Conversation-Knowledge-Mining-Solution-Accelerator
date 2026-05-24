from pydantic import BaseModel
from typing import List


class UserInfo(BaseModel):
    user_name: str | None
    user_principal_id: str | None
    roles: List[str]
    can_access_billing: bool
