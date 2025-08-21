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
    
# --- Esquemas de Canais ---

class RespostaWebchat(BaseModel):
    """Schema de resposta padronizado para o canal de webchat."""
    conteudo_markdown: str
    dados_da_busca: Optional[list] = None
    
class MensagemWhatsapp(BaseModel):
    """Schema de entrada simplificado para um webhook do WhatsApp."""
    wa_id: str # Ex: o número de telefone do cliente
    texto: str

class RespostaWhatsapp(BaseModel):
    """Schema de resposta simples, apenas com texto, para o canal WhatsApp."""
    texto: str