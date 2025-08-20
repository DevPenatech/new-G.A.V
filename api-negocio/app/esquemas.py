# api-negocio/app/esquemas.py

from pydantic import BaseModel, Field 
from typing import Dict, Any, Optional, List, Literal 

# --- Esquemas de Entrada ---
class BuscaQuery(BaseModel):
    query: str
    codfilial: int
    limit: int = 10
    # 2. Adicione o campo 'ordenar_por' abaixo:
    # Usamos Literal para garantir que apenas valores válidos sejam aceitos.
    ordenar_por: Optional[Literal["relevancia", "preco_asc", "preco_desc"]] = "relevancia"


# --- Esquemas de Saída (Representação dos nossos dados) ---

class ProdutoItemBase(BaseModel):
    id: int
    unidade: str
    qtunit: int
    preco: Optional[float] = Field(None, alias='pvenda')
    preco_oferta: Optional[float] = Field(None, alias='poferta')

    class Config:
        from_attributes = True
        populate_by_name = True

class ProdutoBase(BaseModel):
    id: int
    codprod: int
    descricao: Optional[str] = None
    descricaoweb: Optional[str] = None
    marca: Optional[str] = None
    itens: List[ProdutoItemBase] = []

    class Config:
        from_attributes = True

class BuscaResultado(BaseModel):
    resultados: List[ProdutoBase]
    status_busca: str
    
class LogBase(BaseModel):
    sessao_id: str
    mensagem_usuario: str
    resposta_json: Dict[str, Any]

class Feedback(BaseModel):
    sessao_id: str
    tipo: str
    query: str
    resposta_gerada: Dict
    resposta_esperada: Optional[Dict] = None
    
# --- Esquemas de Carrinho ---

class ItemCarrinhoEntrada(BaseModel):
    # O que o usuário envia para adicionar um item
    item_id: int
    quantidade: int
    codfilial: int # Precisamos da filial para saber o preço

class ItemCarrinho(BaseModel):
    # Como um item é representado dentro do carrinho
    item_id: int
    quantidade: int
    descricao_produto: str
    preco_unitario_registrado: float
    subtotal: float

    class Config:
        from_attributes = True

class Carrinho(BaseModel):
    # A representação completa do carrinho
    id: int
    sessao_id: str
    status: str
    itens: List[ItemCarrinho]
    valor_total: float

    class Config:
        from_attributes = True