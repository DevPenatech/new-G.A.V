#from fastapi import FastAPI
#from fastapi.middleware.cors import CORSMiddleware
#from pydantic import BaseModel
#from app.servicos.executor_regras import executar_regras_do_manifesto
#
#
#app = FastAPI()
#
## CORS (ajuste as origens conforme necessário)
#ORIGENS_PERMITIDAS = [
#    "http://localhost:3000",
#    "http://127.0.0.1:3000",
#]
#
#app.add_middleware(
#    CORSMiddleware,
#    allow_origins=ORIGENS_PERMITIDAS,
#    allow_credentials=True,
#    allow_methods=["*"],
#    allow_headers=["*"],
#)
#
#@app.get("/ping")
#async def ping():
#    return {"status": "ok"}
#
#class EntradaChat(BaseModel):
#    texto: str
#    sessao_id: str
#
#@app.post("/chat")
#async def receber_mensagem(body: EntradaChat):
#    saida = executar_regras_do_manifesto(body.model_dump())
#    return saida

# gav-autonomo/app/main.py

# gav-autonomo/app/main.py
"""
FastAPI Otimizado com pre-carregamento de cache e warmup
"""

#import asyncio
#import time
#from fastapi import FastAPI, BackgroundTasks
#from pydantic import BaseModel
#from app.servicos.executor_otimizado import executar_regras_do_manifesto
#from app.cache_otimizado import cache_otimizado
#from app.adaptadores.interface_llm_otimizada import cliente_llm, LLMRequest
#
#app = FastAPI(title="G.A.V. Autonomo - Versão Otimizada")
#
#startup_completed = False
#
#@app.on_event("startup")
#async def startup_event():
#    """Pre-carrega cache e aquece conexões na inicialização"""
#    global startup_completed
#    
#    print("🚀 Iniciando otimizações de startup...")
#    start_time = time.time()
#    
#    # 1. Carrega todos os prompts em cache (paralelo)
#    print("📋 Pre-carregando prompts...")
#    await cache_otimizado.bulk_load_prompts()
#    
#    # 2. Warmup do LLM (primeira chamada sempre é lenta)
#    print("🔥 Aquecendo LLM...")
#    warmup_request = LLMRequest(
#        sistema="Você é um assistente. Responda apenas com um JSON simples.",
#        entrada_usuario="teste",
#        exemplos=[],
#        timeout=30.0
#    )
#    
#    try:
#        await cliente_llm.completar_para_json_async(warmup_request)
#        print("✅ LLM aquecido com sucesso")
#    except Exception as e:
#        print(f"⚠️ Erro no warmup do LLM: {e}")
#    
#    startup_time = time.time() - start_time
#    startup_completed = True
#    print(f"🎯 Startup concluído em {startup_time:.2f}s - Sistema otimizado!")
#
#@app.on_event("shutdown")
#async def shutdown_event():
#    """Limpa conexões na finalização"""
#    await cliente_llm.close()
#    print("🛑 Conexões encerradas")
#
#class EntradaChat(BaseModel):
#    texto: str
#    sessao_id: str
#
#@app.get("/ping")
#async def ping():
#    return {
#        "status": "ok", 
#        "startup_completed": startup_completed,
#        "cache_prompts": len(cache_otimizado.prompts_cache),
#        "cache_contextos": len(cache_otimizado.contextos_cache)
#    }
#
#@app.get("/health")
#async def health():
#    """Endpoint de health check detalhado"""
#    return {
#        "status": "healthy",
#        "startup_completed": startup_completed,
#        "cache_stats": {
#            "prompts_cached": len(cache_otimizado.prompts_cache),
#            "contextos_cached": len(cache_otimizado.contextos_cache),
#        },
#        "optimizations": [
#            "cache_pre_loaded",
#            "llm_warmed_up", 
#            "async_pipeline",
#            "connection_pool"
#        ]
#    }
#
#@app.post("/chat")
#async def receber_mensagem(body: EntradaChat):
#    """Endpoint principal otimizado"""
#    inicio = time.time()
#    
#    # Se o startup não completou, aguarda um pouco
#    if not startup_completed:
#        await asyncio.sleep(0.1)
#    
#    resultado = executar_regras_do_manifesto(body.model_dump())
#    
#    tempo_resposta = time.time() - inicio
#    
#    # Adiciona métricas de performance na resposta
#    if isinstance(resultado, dict):
#        resultado["_performance"] = {
#            "tempo_resposta_ms": round(tempo_resposta * 1000, 2),
#            "cache_hit": tempo_resposta < 1.0  # Indica se foi rápido (provavelmente cache hit)
#        }
#    
#    return resultado
#
#@app.post("/chat/async")
#async def receber_mensagem_async(body: EntradaChat):
#    """Endpoint assíncrono nativo (mais rápido)"""
#    from app.servicos.executor_otimizado import executar_regras_otimizado
#    
#    inicio = time.time()
#    resultado = await executar_regras_otimizado(body.model_dump())
#    tempo_resposta = time.time() - inicio
#    
#    if isinstance(resultado, dict):
#        resultado["_performance"] = {
#            "tempo_resposta_ms": round(tempo_resposta * 1000, 2),
#            "modo": "async_native"
#        }
#    
#    return resultado
#
#@app.post("/cache/reload")
#async def reload_cache():
#    """Endpoint para recarregar cache manualmente"""
#    await cache_otimizado.bulk_load_prompts()
#    return {
#        "status": "cache_reloaded",
#        "prompts_count": len(cache_otimizado.prompts_cache)
#    }
#
#@app.get("/cache/stats")
#async def cache_stats():
#    """Estatísticas detalhadas do cache"""
#    return {
#        "prompts_cache": {
#            "count": len(cache_otimizado.prompts_cache),
#            "keys": list(cache_otimizado.prompts_cache.keys())
#        },
#        "contextos_cache": {
#            "count": len(cache_otimizado.contextos_cache),
#            "sessions": list(cache_otimizado.contextos_cache.keys())
#        },
#        "llm_cache": {
#            "compiled_prompts": len(cliente_llm.prompts_compilados)
#        }
#    }

# gav-autonomo/app/main.py
"""
Versão Corrigida - Sem erros de import
Otimizações básicas funcionais
"""

import time
from fastapi import FastAPI
from pydantic import BaseModel

# Import da versão corrigida
from app.servicos.executor_regras_rapido import (
    executar_regras_do_manifesto_rapido, 
    get_cache_stats
)

app = FastAPI(title="G.A.V. Autonomo - Versão Corrigida")

class EntradaChat(BaseModel):
    texto: str
    sessao_id: str

@app.get("/ping")
async def ping():
    """Endpoint básico de saúde"""
    cache_stats = get_cache_stats()
    return {
        "status": "ok", 
        "version": "otimizada_simples",
        "cache_prompts": cache_stats["cache_size"]
    }

@app.get("/health")
async def health():
    """Health check detalhado"""
    cache_stats = get_cache_stats()
    return {
        "status": "healthy",
        "optimizations": ["cache_basico", "timeout_reduzido", "exemplos_limitados"],
        "cache_stats": cache_stats
    }

@app.post("/chat")
async def receber_mensagem(body: EntradaChat):
    """Endpoint principal com otimizações básicas"""
    inicio = time.time()
    
    # Usa a versão otimizada simples (sem problemas de import)
    resultado = executar_regras_do_manifesto_rapido(body.model_dump())
    
    tempo_resposta = time.time() - inicio
    
    # Adiciona métricas se não existirem
    if isinstance(resultado, dict) and "_performance" not in resultado:
        resultado["_performance"] = {
            "tempo_resposta_ms": round(tempo_resposta * 1000, 2),
            "versao": "simples_corrigida"
        }
    
    return resultado

@app.get("/cache/stats")
async def cache_stats():
    """Estatísticas do cache"""
    return get_cache_stats()

@app.post("/cache/clear")
async def clear_cache():
    """Limpa o cache (para debugging)"""
    from app.servicos.executor_regras_rapido import CACHE_PROMPTS
    CACHE_PROMPTS.clear()
    return {"status": "cache_cleared"}