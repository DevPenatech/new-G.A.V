from pydantic import BaseModel
from typing import Literal

class ParametrosBusca(BaseModel):
    query: str
    ordenar_por: str | None = None

class ParametrosAdicao(BaseModel):
    item_id: str
    quantidade: int

class SaidaTool(BaseModel):
    tool_name: Literal["buscar_produtos", "adicionar_item_carrinho", "ver_carrinho"]
    parameters: dict

def validar_json_contra_schema(json_dado, schema):
    from jsonschema import validate, ValidationError

    try:
        validate(instance=json_dado, schema=schema)
        return True
    except ValidationError as e:
        return False
