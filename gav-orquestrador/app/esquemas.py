# gav-orquestrador/app/esquemas.py

from pydantic import BaseModel
from typing import Dict, Any, Optional

class MensagemChat(BaseModel):
    texto: str
    sessao_id: str

class ToolCall(BaseModel):
    tool_name: str
    parameters: Dict[str, Any]

class Feedback(BaseModel):
    sessao_id: str
    tipo: str
    query: str
    resposta_gerada: Dict
    resposta_esperada: Optional[Dict] = None