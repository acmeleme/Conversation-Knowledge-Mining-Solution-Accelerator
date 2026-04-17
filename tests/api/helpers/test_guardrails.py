import sys
import os
SRC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../src'))
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)
import pytest
from src.api.helpers.guardrails import is_in_scope

@pytest.mark.parametrize("query,expected", [
    ("Como está a satisfação dos clientes?", True),
    ("Quais são os tópicos mais frequentes nas chamadas?", True),
    ("Me mostre o tempo médio de atendimento", True),
    ("Como fazer um bolo de chocolate?", False),
    ("Qual a capital da França?", False),
    ("Explique a teoria da relatividade", False),
    ("Resumo das reclamações de billing", True),
    ("Como configurar o roteador?", False),
    ("Quantas chamadas foram resolvidas ontem?", True),
])
def test_is_in_scope(query, expected):
    assert is_in_scope(query) == expected
