from pydantic import BaseModel
from typing import Dict, Any
import json, pathlib

class ToolCall(BaseModel):
    tool_name: str           # nome da ferramenta decidido pelo LLM
    parameters: Dict[str, Any]  # payload arbitrário, decidido pelo prompt
# JSON Schema mínimo (só estrutura; nada de enum/listas de campos)
MANIFEST_SCHEMA_TOOL_SELECTOR = {
    "type": "object",
     "properties": {
         "tool_name": { "type": "string" },
         "parameters": { "type": "object" }
     },
     "required": ["tool_name", "parameters"],
     "additionalProperties": False
 }

def carregar_schema(schema_ref: Any) -> dict:
    """Aceita dict pronto OU caminho para JSON (string) e retorna dict."""
    if isinstance(schema_ref, dict):
        return schema_ref
    if isinstance(schema_ref, str):
        p = pathlib.Path(schema_ref)
        with p.open(encoding="utf-8") as f:
            return json.load(f)
    raise TypeError("schema deve ser dict ou caminho para arquivo .json")