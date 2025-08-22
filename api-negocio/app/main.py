# api-negocio/app/main.py

from fastapi import FastAPI, Depends, HTTPException, Body
from typing import List
from sqlalchemy.orm import Session

from . import database, esquemas
from . import crud  # agora existe (vide arquivo novo)

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

@app.get("/unidades/aliases", tags=["Unidades"])
def endpoint_get_unidade_aliases(db: Session = Depends(get_db)):
    """Retorna um dicionário de todos os aliases de unidade ativos."""
    rows = crud.get_all_unidade_aliases(db)
    # Converte a lista de dicts em dict alias->unidade_principal
    return {row["alias"]: row["unidade_principal"] for row in rows}

# --- Endpoints de ADMIN ---
@app.get("/admin/prompts/buscar", tags=["Admin"])
def admin_buscar_prompt(nome: str, espaco: str = "legacy", versao: str = "v1", db: Session = Depends(get_db)):
    """
    Busca um template de prompt ativo por (nome, espaco, versao).
    """
    tpl = crud.get_prompt_ativo_por_nome_espaco_versao(db, nome=nome, espaco=espaco, versao=versao)
    if not tpl:
        raise HTTPException(status_code=404, detail="Prompt não encontrado para os filtros informados.")
    return tpl

@app.get("/admin/prompts/{prompt_id}/exemplos/ativos", tags=["Admin"])
def admin_listar_exemplos_ativos(prompt_id: int, db: Session = Depends(get_db)):
    """
    Lista exemplos ativos (few-shot) de um prompt.
    """
    return crud.get_prompt_exemplos_ativos(db, prompt_id=prompt_id)


@app.get("/admin/prompts", response_model=List[esquemas.Prompt], tags=["Admin"])
def admin_listar_prompts(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Lista todos os templates de prompt no sistema."""
    prompts = crud.get_all_prompts(db, skip=skip, limit=limit)
    return prompts

@app.post("/admin/prompts", response_model=esquemas.Prompt, status_code=201, tags=["Admin"])
def admin_criar_prompt(prompt: esquemas.PromptCreate, db: Session = Depends(get_db)):
    """Cria um novo template de prompt."""
    return crud.create_prompt(db=db, prompt=prompt)

@app.patch("/admin/prompts/{prompt_id}/status", response_model=esquemas.Prompt, tags=["Admin"])
def admin_atualizar_status_prompt(prompt_id: int, update_data: esquemas.PromptUpdate, db: Session = Depends(get_db)):
    """
    Atualiza o status de um prompt (ativo/inativo).
    """
    db_prompt = crud.get_prompt(db, prompt_id=prompt_id)
    if db_prompt is None:
        raise HTTPException(status_code=404, detail="Prompt não encontrado.")
    return crud.update_prompt_status(db=db, prompt_id=prompt_id, ativo=update_data.ativo)


@app.get("/admin/produtos/{produto_id}/aliases", response_model=List[esquemas.ProdutoAlias], tags=["Admin"])
def admin_listar_aliases_produto(produto_id: int, db: Session = Depends(get_db)):
    """Lista todos os aliases de um produto específico."""
    return crud.get_produto_aliases(db, produto_id=produto_id)

@app.post("/admin/produtos/{produto_id}/aliases", response_model=esquemas.ProdutoAlias, status_code=201, tags=["Admin"])
def admin_criar_alias_produto(produto_id: int, alias: esquemas.ProdutoAliasCreate, db: Session = Depends(get_db)):
    """Cria um novo alias (apelido) para um produto."""
    # Poderíamos adicionar uma verificação aqui para ver se o produto_id existe
    return crud.create_produto_alias(db=db, alias=alias, produto_id=produto_id)

@app.post("/admin/prompts/{prompt_id}/exemplos", response_model=esquemas.PromptExemplo, status_code=201, tags=["Admin"])
def admin_criar_exemplo_prompt(prompt_id: int, exemplo: esquemas.PromptExemploCreate, db: Session = Depends(get_db)):
    """Adiciona um novo exemplo de ensino (few-shot) para um prompt."""
    return crud.create_prompt_exemplo(db=db, prompt_id=prompt_id, exemplo=exemplo)

# === NOVOS ENDPOINTS: PROMPTS (aderente ao seu banco) ===
@app.get("/admin/prompts/por-nome", tags=["Admin"])
def admin_get_prompt_por_nome(nome: str, espaco: str, versao: int, db: Session = Depends(get_db)):
    """
    Retorna um prompt ativo filtrando por nome + espaco + versao.
    """
    prompt = crud.get_prompt_por_nome_espaco_versao(db, nome=nome, espaco=espaco, versao=versao)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt não encontrado.")
    return prompt

@app.get("/admin/prompts/{prompt_id}/exemplos", response_model=List[esquemas.PromptExemplo], tags=["Admin"])
def admin_listar_exemplos_prompt(prompt_id: int, db: Session = Depends(get_db)):
    """
    Lista exemplos (few-shot) de um prompt.
    """
    return crud.get_prompt_exemplos(db, prompt_id=prompt_id)