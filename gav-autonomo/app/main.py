# gav-autonomo/app/main.py
"""
Sistema Final - Qwen2:7b Otimizado
Performance + Formatação Rica Original
"""

import time
from fastapi import FastAPI
from pydantic import BaseModel

# Import do executor qwen2 otimizado
from app.servicos.executor_qwen2_otimizado import (
    executar_regras_qwen2_otimizado, 
    get_stats_qwen2_otimizado
)

app = FastAPI(title="G.A.V. Autonomo - Qwen2 Otimizado Final")

class EntradaChat(BaseModel):
    texto: str
    sessao_id: str

@app.get("/ping")
async def ping():
    """Status do sistema final"""
    stats = get_stats_qwen2_otimizado()
    return {
        "status": "ok", 
        "version": "QWEN2_OTIMIZADO_FINAL",
        "modelo": stats["modelo_unico"],
        "cache_size": stats["cache_prompts"],
        "performance": stats["performance_target"]
    }

@app.get("/health")
async def health():
    """Health check do sistema final"""
    stats = get_stats_qwen2_otimizado()
    return {
        "status": "healthy",
        "version": "QWEN2_OTIMIZADO_FINAL",
        "arquitetura": {
            "modelo_unico": stats["modelo_unico"],
            "configuracoes": stats["configuracoes"],
            "estrategia": "Um modelo, duas configurações otimizadas"
        },
        "performance_target": stats["performance_target"],
        "features": [
            "formatacao_original_com_ids_numerados",
            "emojis_contextuais",
            "call_to_action_claro",
            "cache_agressivo_duplo",
            "contexto_estruturado_completo"
        ]
    }

@app.post("/chat")
async def receber_mensagem(body: EntradaChat):
    """Endpoint final otimizado"""
    inicio = time.time()
    
    # Executor Qwen2:7b otimizado
    resultado = executar_regras_qwen2_otimizado(body.model_dump())
    
    tempo_resposta = time.time() - inicio
    
    # Performance sempre presente
    if isinstance(resultado, dict):
        if "_performance" not in resultado:
            resultado["_performance"] = {}
        
        resultado["_performance"].update({
            "tempo_total_ms": round(tempo_resposta * 1000, 2),
            "versao": "QWEN2_OTIMIZADO_FINAL"
        })
    
    return resultado

@app.get("/comparacao/versoes")
async def comparacao_versoes():
    """Compara todas as versões implementadas"""
    return {
        "evolucao_performance": {
            "original_lento": "15-17s (qwen2:7b + 42 exemplos + timeout 60s)",
            "hibrido_phi3": "1.4s (phi3:mini rápido + templates básicos)",
            "qwen2_otimizado": "3-5s (qwen2:7b + configurações específicas + formatação rica)"
        },
        "comparacao_formatacao": {
            "original": "IDs numerados + emojis + contexto completo",
            "phi3_templates": "Formatação básica, sem IDs numerados",
            "qwen2_otimizado": "Formatação original COMPLETA + IDs numerados"
        },
        "melhor_estrategia": {
            "decisao": "Use qwen2_otimizado para tudo",
            "motivo": "Equilibra velocidade (3-5s) com qualidade original",
            "vantagem": "Formatação rica igual ao git original, mas 70% mais rápido"
        }
    }

@app.get("/cache/stats")
async def cache_stats():
    """Stats detalhadas do cache"""
    return get_stats_qwen2_otimizado()

@app.post("/cache/clear")
async def clear_cache():
    """Limpa cache"""
    from app.servicos.executor_qwen2_otimizado import CACHE_PROMPTS, CACHE_RESPOSTAS_LLM
    CACHE_PROMPTS.clear()
    CACHE_RESPOSTAS_LLM.clear()
    return {"status": "cache_cleared", "version": "QWEN2_OTIMIZADO_FINAL"}

@app.get("/modelo/configuracoes")
async def modelo_configuracoes():
    """Mostra configurações específicas por tarefa"""
    return {
        "modelo_base": "qwen2:7b",
        "configuracao_decisao": {
            "timeout": "5s",
            "max_tokens": 200,
            "temperature": 0.05,
            "exemplos": "máximo 2",
            "objetivo": "Velocidade e consistência",
            "tempo_esperado": "1-2s"
        },
        "configuracao_apresentacao": {
            "timeout": "10s", 
            "max_tokens": 800,
            "temperature": 0.15,
            "exemplos": "completos",
            "objetivo": "Formatação rica com IDs numerados",
            "tempo_esperado": "2-4s"
        },
        "resultado_final": "3-5s total com formatação original mantida"
    }