from pydantic import BaseModel
from typing import Literal, Union, Dict, Any
from pathlib import Path
import json

class ToolCall(BaseModel):
    tool_name: str           # nome da ferramenta decidido pelo LLM
    parameters: Dict[str, Any]  # payload arbitrário, decidido pelo prompt
# JSON Schema mínimo (só estrutura; nada de enum/listas de campos)
MANIFEST_SCHEMA_TOOL_SELECTOR = {
    "type": "object",
    "properties": {
        "tool_name": {"type": "string"},
        "parameters": {"type": "object"}
    },
    "required": ["tool_name", "parameters"],
    "additionalProperties": False
}

def validar_json_contra_schema(json_dado: Dict[str, Any], schema: Dict[str, Any]) -> bool:
    """
    Valida um JSON contra um JSON Schema. Retorna True/False.
    (Sem regras de negócio; só estrutura.)
    """
    try:
        from jsonschema import validate
        validate(instance=json_dado, schema=schema)
        return True
    except Exception:
        return False

# === Loader de schemas robusto ===
# Aceita dict pronto OU nome/relativo/absoluto de arquivo .json
APP_DIR = Path(__file__).resolve().parents[1]               # .../app
SCHEMAS_DIR = APP_DIR / "validadores" / "esquemas"          # .../app/validadores/esquemas

def _resolver_caminho_schema(schema_name_or_path: str) -> Path:
    p = Path(schema_name_or_path)
    # Absoluto e existente
    if p.is_absolute() and p.exists():
        return p
    # Só o nome: tenta em app/validadores/esquemas
    candidato = SCHEMAS_DIR / p.name
    if candidato.exists():
        return candidato
    # Caminho relativo a app/
    relativo_app = APP_DIR / p
    if relativo_app.exists():
        return relativo_app
    # Último recurso: relativo ao CWD
    if p.exists():
        return p
    raise FileNotFoundError(
        f"Schema não encontrado: '{schema_name_or_path}'. "
        f"Tentado: {candidato}, {relativo_app}, {p}"
    )

def carregar_schema(schema_ref: Any) -> Dict[str, Any]:
    """
    Aceita:
      - dict (retorna como está)
      - string com nome do arquivo (ex.: 'decisao_llm.json')
      - string com caminho relativo/absoluto
    """
    if isinstance(schema_ref, dict):
        return schema_ref
    if isinstance(schema_ref, str):
        caminho = _resolver_caminho_schema(schema_ref)
        with caminho.open(encoding="utf-8") as f:
            return json.load(f)
    raise TypeError("schema deve ser um dict ou um caminho (str) para .json")