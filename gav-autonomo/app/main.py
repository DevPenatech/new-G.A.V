# gav-autonomo/app/main.py
# VERSÃO ORIGINAL DO GIT - Simples e Funcional

from fastapi import FastAPI
from pydantic import BaseModel
from app.servicos.executor_regras import executar_regras_do_manifesto

app = FastAPI(
    title="GAV Autônomo - Versão Original Git",
    description="Volta para a versão que funcionava, com métricas detalhadas de tempo",
    version="git-original-com-metricas"
)

@app.get("/ping")
async def ping():
    return {
        "status": "ok",
        "versao": "git-original",
        "metricas": "ativadas"
    }

class EntradaChat(BaseModel):
    texto: str
    sessao_id: str

@app.post("/chat")
async def receber_mensagem(body: EntradaChat):
    """
    Endpoint original do git com métricas de tempo detalhadas
    
    Vai mostrar exatamente onde está gastando tempo:
    - Busca de prompts
    - LLM decisão
    - Validação
    - API calls
    - LLM apresentação
    """
    saida = executar_regras_do_manifesto(body.model_dump())
    return saida

@app.get("/healthcheck")
async def healthcheck():
    return {
        "status": "healthy",
        "versao": "git-original",
        "debug_timing": "enabled",
        "funcionalidades": [
            "busca_produtos",
            "carrinho_completo", 
            "apresentacao_rica",
            "contexto_numerado",
            "metricas_detalhadas"
        ]
    }