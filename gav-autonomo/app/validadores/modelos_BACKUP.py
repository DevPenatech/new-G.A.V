from typing import Any, Dict
from jsonschema import validate, ValidationError
from pathlib import Path
import json

# Schemas genéricos (ensináveis via prompt; sem regras de negócio)
SCHEMAS: Dict[str, Dict[str, Any]] = {
    "api_or_chat": {
        "type": "object",
        "properties": {
            "action":   {"type": "string", "enum": ["api_call", "respond_text"]},
            "endpoint": {"type": "string"},
            "method":   {"type": "string"},
            "payload":  {"type": "object"},
            "headers":  {"type": "object"},
            "text":     {"type": "string"}
        },
        "required": ["action"],
        "additionalProperties": True
    }
}

def validar_json_contra_schema(json_dado: Dict[str, Any], schema: Dict[str, Any]) -> bool:
    try:
        validate(instance=json_dado, schema=schema)
        return True
    except ValidationError:
        return False

def carregar_schema(schema_ref: Any) -> Dict[str, Any]:
    """
    Aceita:
      - dict (schema pronto)
      - '#nome' (carrega SCHEMAS[nome])
      - caminho para arquivo .json
    """
    if isinstance(schema_ref, dict):
        return schema_ref
    if isinstance(schema_ref, str):
        if schema_ref.startswith("#"):
            nome = schema_ref[1:]
            if nome in SCHEMAS:
                return SCHEMAS[nome]
            raise KeyError(f"Schema embutido '{nome}' não encontrado.")
        p = Path(schema_ref)
        with p.open(encoding="utf-8") as f:
            return json.load(f)
    raise TypeError("schema_ref deve ser dict, '#nome' ou caminho para arquivo .json")