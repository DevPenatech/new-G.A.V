# gav-autonomo/app/main.py
"""
Sistema Híbrido Inteligente:
- PHI3:mini para decisões (0.04s)
- Qwen2:7b seletivo para apresentação rica (3s quando necessário)
- Templates rápidos para casos simples
"""

import time
from fastapi import FastAPI
from pydantic import BaseModel

# Import do executor híbrido
from app.servicos.executor_hibrido_inteligente import (
    executar_regras_hibrido_inteligente, 
    get_stats_hibrido
)

app = FastAPI(title="G.A.V. Autonomo - Sistema Híbrido Inteligente")

class EntradaChat(BaseModel):
    texto: str
    sessao_id: str

@app.get("/ping")
async def ping():
    """Status do sistema híbrido"""
    stats = get_stats_hibrido()
    return {
        "status": "ok", 
        "version": "HIBRIDO_INTELIGENTE_v1",
        "modelo_decisao": stats["modelo_decisao"],
        "modelo_apresentacao": stats["modelo_apresentacao"],
        "cache_size": stats["cache_prompts"]
    }

@app.get("/health")
async def health():
    """Health check detalhado"""
    stats = get_stats_hibrido()
    return {
        "status": "healthy",
        "version": "HIBRIDO_INTELIGENTE_v1",
        "arquitetura": {
            "decisoes": f"{stats['modelo_decisao']} (0.04s)",
            "apresentacao_simples": "templates (0.1s)",
            "apresentacao_rica": f"{stats['modelo_apresentacao']} (3s)",
            "estrategia": stats["estrategia"]
        },
        "performance_target": stats["performance_target"],
        "cache_stats": {
            "prompts": stats["cache_prompts"],
            "llm_responses": stats["cache_llm_responses"]
        }
    }

@app.post("/chat")
async def receber_mensagem(body: EntradaChat):
    """Endpoint híbrido inteligente"""
    inicio = time.time()
    
    # Executor híbrido que decide qual modelo usar
    resultado = executar_regras_hibrido_inteligente(body.model_dump())
    
    tempo_resposta = time.time() - inicio
    
    # Performance sempre presente
    if isinstance(resultado, dict):
        if "_performance" not in resultado:
            resultado["_performance"] = {}
        
        resultado["_performance"].update({
            "tempo_total_ms": round(tempo_resposta * 1000, 2),
            "versao": "HIBRIDO_INTELIGENTE_v1"
        })
    
    return resultado

@app.get("/estrategia/explicacao")
async def explicar_estrategia():
    """Explica como funciona a estratégia híbrida"""
    return {
        "conceito": "Usa o modelo mais adequado para cada tarefa",
        "fases": {
            "1_decisao": {
                "modelo": "phi3:mini",
                "tempo": "0.04s",
                "funcao": "Classifica intenção, decide API call"
            },
            "2_api": {
                "processo": "HTTP request",
                "tempo": "0.2s",
                "funcao": "Busca dados, executa operação"
            },
            "3_apresentacao": {
                "avaliacao": "Analisa complexidade da resposta",
                "opcoes": {
                    "simples": "Template rápido (0.1s)",
                    "media": "Template ou LLM com timeout baixo",
                    "complexa": "Qwen2:7b completo (3s)"
                }
            }
        },
        "criterios_complexidade": {
            "simples": ["Adição ao carrinho", "Carrinho vazio", "Confirmações"],
            "media": ["2-4 produtos", "Carrinho pequeno", "Operações básicas"],
            "complexa": ["5+ produtos", "Comparações", "Recomendações", "Contexto rico"]
        },
        "exemplo_fluxo": {
            "busca_simples": "PHI3(0.04s) → API(0.2s) → Template(0.1s) = 0.34s",
            "busca_complexa": "PHI3(0.04s) → API(0.2s) → Qwen2(3s) = 3.24s",
            "cache_hit": "PHI3_cache(0.01s) → API(0.2s) → Template(0.1s) = 0.31s"
        }
    }

@app.get("/debug/complexidade")
async def debug_complexidade():
    """Testa análise de complexidade"""
    from app.servicos.executor_hibrido_inteligente import analisar_complexidade_resposta
    
    casos_teste = [
        {
            "caso": "Carrinho vazio",
            "dados": {"itens": [], "valor_total": 0},
            "mensagem": "meu carrinho"
        },
        {
            "caso": "Busca simples",
            "dados": {"resultados": [{"id": 1, "itens": [{"id": 101}]}]},
            "mensagem": "buscar chocolate"
        },
        {
            "caso": "Busca complexa",
            "dados": {"resultados": [
                {"id": 1, "itens": [{"id": 101}, {"id": 102}]},
                {"id": 2, "itens": [{"id": 201}, {"id": 202}, {"id": 203}]},
                {"id": 3, "itens": [{"id": 301}]}
            ]},
            "mensagem": "qual o melhor chocolate"
        },
        {
            "caso": "Adição carrinho",
            "dados": {"status": "item adicionado", "carrinho_id": 123},
            "mensagem": "coloque 5 do produto 456"
        }
    ]
    
    resultados = []
    for caso in casos_teste:
        complexidade = analisar_complexidade_resposta(caso["dados"], caso["mensagem"])
        resultados.append({
            "caso": caso["caso"],
            "complexidade_detectada": complexidade,
            "modelo_recomendado": "template" if complexidade == "simples" else "qwen2:7b",
            "tempo_estimado": "0.1s" if complexidade == "simples" else "3s"
        })
    
    return {"analise_casos": resultados}

@app.get("/cache/stats")
async def cache_stats():
    """Stats do sistema híbrido"""
    return get_stats_hibrido()

@app.post("/cache/clear")
async def clear_cache():
    """Limpa cache do sistema híbrido"""
    from app.servicos.executor_hibrido_inteligente import CACHE_PROMPTS, CACHE_RESPOSTAS_LLM
    CACHE_PROMPTS.clear()
    CACHE_RESPOSTAS_LLM.clear()
    return {"status": "cache_cleared", "version": "HIBRIDO_INTELIGENTE_v1"}

@app.get("/benchmark")
async def benchmark_modelos():
    """Compara performance dos diferentes approaches"""
    return {
        "cenarios": {
            "busca_simples_1_produto": {
                "template": "0.34s",
                "llm_sempre": "3.24s",
                "hibrido": "0.34s (usa template)",
                "economia": "89% mais rápido que LLM sempre"
            },
            "busca_complexa_10_produtos": {
                "template": "0.34s (formatação limitada)",
                "llm_sempre": "3.24s (formatação rica)",
                "hibrido": "3.24s (usa LLM para riqueza)",
                "beneficio": "Qualidade mantida quando necessário"
            },
            "adicao_carrinho": {
                "template": "0.31s",
                "llm_sempre": "3.21s",
                "hibrido": "0.31s (usa template)",
                "economia": "90% mais rápido para operação simples"
            }
        },
        "estrategia": "Melhor dos mundos: velocidade para casos simples, riqueza para casos complexos"
    }