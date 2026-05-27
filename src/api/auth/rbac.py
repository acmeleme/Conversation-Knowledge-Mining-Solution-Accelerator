from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from auth.auth_utils import DEFAULT_DEV_ROLE, can_access_billing, get_user_roles

# Tópicos de Cartão de Crédito restritos ao role 'financeiro'
# Devem corresponder exatamente ao campo 'topic' na tabela processed_data do SQL.
RESTRICTED_TOPIC = "Cartao de Credito — Fatura e Pagamento"  # compatibilidade legada
RESTRICTED_TOPICS = [
    "Cartao de Credito — Fatura e Pagamento",
    "Cartao de Credito — Bloqueio e Contestacao",
]


def get_current_user_roles(request: Request) -> list[str]:
    """FastAPI dependency that returns EasyAuth app roles for the current request."""
    roles = get_user_roles(request.headers)
    return roles or [DEFAULT_DEV_ROLE]


def require_role(required_roles: list[str]) -> Callable[[list[str]], list[str]]:
    """Create a dependency that enforces membership in at least one required role."""
    normalized_required_roles = {role.casefold() for role in required_roles}

    def dependency(
        roles: Annotated[list[str], Depends(get_current_user_roles)],
    ) -> list[str]:
        if not normalized_required_roles:
            return roles

        normalized_user_roles = {role.casefold() for role in roles}
        if normalized_user_roles.isdisjoint(normalized_required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para acessar este recurso.",
            )

        return roles

    return dependency


def filter_topics_by_role(topics: list[str], roles: list[str]) -> list[str]:
    """Oculta os tópicos de Cartão de Crédito a menos que o usuário tenha o role 'financeiro'."""
    if can_access_billing(roles):
        return topics

    return [topic for topic in topics if topic not in RESTRICTED_TOPICS]