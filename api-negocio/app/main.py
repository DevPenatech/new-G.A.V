# api-negocio/app/main.py

from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

from . import database, crud, esquemas

app = FastAPI(
    title="API de Negócio - G.A.V.",
    description="Este serviço gerencia toda a lógica de negócio.",
    version="1.0.0"
)

# --- Dependência para obter a sessão do banco ---
# Este é o padrão do FastAPI para gerenciar sessões de banco de dados por requisição.
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Endpoints ---

@app.get("/healthcheck", tags=["Monitoring"])
def health_check():
    db_status = database.testar_conexao()
    return {"status": "ok", "service": "API de Negócio", "db_status": db_status}

@app.post("/produtos/busca", response_model=esquemas.BuscaResultado, tags=["Produtos"])
def endpoint_buscar_produtos(query: esquemas.BuscaQuery, db: Session = Depends(get_db)):
    # A função agora retorna um dicionário, que passamos diretamente
    resultado_busca = crud.buscar_produtos(
        db, query=query.query, limit=query.limit,
        ordenar_por=query.ordenar_por, codfilial=query.codfilial
    )
    return resultado_busca

# Adicione estes endpoints ao final do arquivo
@app.post("/logs/interacao", tags=["Logs"], status_code=201)
def endpoint_criar_log(log_data: esquemas.LogBase, db: Session = Depends(get_db)):
    log_id = crud.criar_log_interacao(db, log=log_data)
    return {"log_id": log_id}

@app.patch("/logs/feedback", tags=["Logs"], status_code=200)
def endpoint_patch_feedback(feedback_data: esquemas.Feedback, db: Session = Depends(get_db)):
    crud.atualizar_log_com_feedback(db, feedback=feedback_data)
    return {"status": "feedback registrado"}


@app.post("/carrinhos/{sessao_id}/itens", tags=["Carrinho"], status_code=201)
def endpoint_adicionar_item(sessao_id: str, item: esquemas.ItemCarrinhoEntrada, db: Session = Depends(get_db)):
    """
    Adiciona um item ao carrinho de uma sessão.
    Cria o carrinho se ele não existir.
    """
    carrinho = crud.get_ou_criar_carrinho_por_sessao(db, sessao_id=sessao_id)
    if not carrinho:
        raise HTTPException(status_code=404, detail="Não foi possível criar ou encontrar o carrinho.")
    
    try:
        crud.adicionar_item_ao_carrinho(db, carrinho_id=carrinho['id'], item_data=item)
        return {"status": "item adicionado", "carrinho_id": carrinho['id']}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/carrinhos/{sessao_id}", response_model=esquemas.Carrinho, tags=["Carrinho"])
def endpoint_ver_carrinho(sessao_id: str, db: Session = Depends(get_db)):
    """
    Retorna o conteúdo detalhado do carrinho de uma sessão.
    """
    carrinho_base = crud.get_ou_criar_carrinho_por_sessao(db, sessao_id=sessao_id)
    if not carrinho_base:
        raise HTTPException(status_code=404, detail="Carrinho não encontrado.")
        
    carrinho_detalhado = crud.get_carrinho_detalhado(db, carrinho_id=carrinho_base['id'])
    if not carrinho_detalhado:
        raise HTTPException(status_code=404, detail="Detalhes do carrinho não encontrados.")
        
    return carrinho_detalhado

@app.get("/prompts/{nome}", tags=["Prompts"])
def endpoint_get_prompt(nome: str, db: Session = Depends(get_db)):
    """
    Endpoint para buscar um template de prompt ativo pelo nome.
    O orquestrador usará isso para buscar suas instruções.
    """
    template = crud.get_prompt_ativo_por_nome(db, nome=nome)
    if not template:
        raise HTTPException(status_code=404, detail="Prompt não encontrado.")
    return {"nome": nome, "template": template}