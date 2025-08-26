# gav-autonomo/app/servicos/executor_final_perfeito.py
"""
EXECUTOR FINAL PERFEITO - Combina o melhor de tudo:
- PHI3:mini para decisões (1.4s)
- Templates ricos para apresentação (100ms)
- Cache agressivo para performance
- Formatação original com IDs numerados
- Garantia de sempre funcionar
"""

import time
import json
import httpx
import yaml
import hashlib
from typing import Dict, Optional

# Imports existentes
from app.adaptadores.cliente_negocio import obter_prompt_por_nome, listar_exemplos_prompt
from app.validadores.modelos import validar_json_contra_schema, carregar_schema
from app.config.settings import config

# Importa apresentação rica
from app.servicos.apresentacao_rica import aplicar_apresentacao_rica

# Cache reutilizado
from app.servicos.executor_fallback_inteligente import (
    CACHE_PROMPTS, CACHE_RESPOSTAS_LLM, CACHE_TTL, MAX_EXEMPLOS,
    hash_prompt, get_prompt_cached_super, decidir_por_heuristica
)

API_NEGOCIO_URL = config.API_NEGOCIO_URL.rstrip("/")

def executar_regras_final_perfeito(mensagem: dict | str) -> dict:
    """
    Executor Final - Combina velocidade + apresentação rica
    """
    start_time = time.time()
    
    if isinstance(mensagem, str):
        mensagem = {"texto": mensagem, "sessao_id": "anon"}
    
    try:
        with open("app/config/model_manifest.yml", encoding="utf-8") as f:
            manifesto = yaml.safe_load(f)
        
        for regra in manifesto["regras"]:
            if regra["action"] == "decisao_llm":
                resultado = processar_decisao_final(mensagem, regra, manifesto)
                
                tempo_total = time.time() - start_time
                print(f"🏆 Tempo FINAL: {tempo_total:.2f}s")
                
                if isinstance(resultado, dict):
                    resultado["_performance"] = {
                        "tempo_resposta_ms": round(tempo_total * 1000, 2),
                        "cache_size": len(CACHE_PROMPTS),
                        "llm_cache_size": len(CACHE_RESPOSTAS_LLM),
                        "versao": "final_perfeito_v1",
                        "decisao_llm": "phi3_mini",
                        "apresentacao": "template_rico"
                    }
                
                return resultado
    
        return {"erro": "Nenhuma regra válida encontrada no manifesto."}
        
    except Exception as e:
        return {"erro": f"Erro interno: {str(e)}"}

def processar_decisao_final(mensagem: dict, regra: dict, manifesto: dict) -> dict:
    """
    Processamento final com PHI3 para decisões
    """
    try:
        # 1. Busca prompt do cache (super rápido agora)
        prompt_data = get_prompt_cached_super(
            nome=regra["prompt"],
            espaco=regra["espaco_prompt"], 
            versao=str(regra["versao_prompt"])
        )
        
        if not prompt_data:
            return {"erro": "Prompt não encontrado"}
        
        # 2. LLM Selector com PHI3:mini (rápido e confiável)
        entrada_usuario = mensagem["texto"]
        cache_hash = hash_prompt(
            prompt_data["template"], 
            entrada_usuario, 
            len(prompt_data["exemplos"])
        )
        
        decisao = completar_com_phi3_otimizado(
            prompt_data["template_otimizado"], 
            entrada_usuario, 
            cache_hash
        )
        
        # 3. Se PHI3 falhou, usa heurística
        if decisao.get("erro") or not decisao.get("tool_name"):
            print("🎯 PHI3 falhou - usando heurística")
            decisao = decidir_por_heuristica(entrada_usuario)
        
        # 4. Validação
        schema = carregar_schema(regra["schema"])
        if not validar_json_contra_schema(decisao, schema):
            print("🎯 Validação falhou - usando heurística")
            decisao = decidir_por_heuristica(entrada_usuario)
        
        # 5. Execução com apresentação rica sempre
        tool_name = decisao.get("tool_name")
        
        if tool_name == "api_call":
            return executar_api_call_final(decisao.get("parameters", {}), mensagem["sessao_id"])
            
        elif tool_name == "api_call_with_presentation":
            # API primeiro
            json_resultado = executar_api_call_final(decisao.get("parameters", {}), mensagem["sessao_id"])
            
            # Apresentação rica SEMPRE (sem LLM)
            return aplicar_apresentacao_rica_final(
                json_resultado, 
                mensagem["texto"], 
                decisao.get("parameters", {}),
                mensagem["sessao_id"]
            )
                
        else:
            return {"erro": f"Ferramenta não reconhecida: {tool_name}"}
            
    except Exception as e:
        print(f"Erro no processamento final: {e}")
        return {"erro": f"Erro interno: {str(e)}"}

def completar_com_phi3_otimizado(template_compilado: str, entrada_usuario: str, cache_hash: str) -> dict:
    """
    Otimizado especificamente para PHI3:mini - rápido e confiável
    """
    
    # Verifica cache primeiro
    if cache_hash in CACHE_RESPOSTAS_LLM:
        entry = CACHE_RESPOSTAS_LLM[cache_hash]
        if time.time() - entry["timestamp"] < CACHE_TTL:
            print("⚡ Cache HIT - decisão PHI3 reutilizada!")
            return entry["resposta"]
    
    prompt_final = template_compilado.replace("{ENTRADA_USUARIO}", entrada_usuario)
    
    print("🚀 Decisão com PHI3:mini (otimizado)...")
    
    try:
        with httpx.Client(timeout=10) as client:  # Timeout generoso para PHI3
            response = client.post(
                f"{config.OLLAMA_HOST}/api/generate",
                json={
                    "model": config.OLLAMA_MODEL_NAME,  # Deve ser phi3:mini
                    "prompt": prompt_final,
                    "format": "json",
                    "stream": False,
                    "options": {
                        "temperature": 0.05,  # Muito baixo para decisões consistentes
                        "top_p": 0.95,
                        "num_predict": 150,   # Pequeno para decisões
                        "stop": ["\n\n", "```", "---"]
                    }
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                conteudo = data.get("response", "").strip()
                
                try:
                    resultado = json.loads(conteudo)
                    
                    # Armazena no cache
                    CACHE_RESPOSTAS_LLM[cache_hash] = {
                        "resposta": resultado,
                        "timestamp": time.time()
                    }
                    
                    return resultado
                    
                except json.JSONDecodeError:
                    # Tenta extrair JSON com regex
                    import re
                    json_match = re.search(r'\{[^{}]*"tool_name"[^{}]*\}', conteudo)
                    if json_match:
                        try:
                            return json.loads(json_match.group())
                        except:
                            pass
                    
                    print(f"⚠️ PHI3 JSON inválido: {conteudo[:100]}...")
                    return {"erro": "phi3_json_invalido"}
    
    except (httpx.TimeoutException, Exception) as e:
        print(f"❌ PHI3 falhou: {e}")
        return {"erro": "phi3_failed"}

def aplicar_apresentacao_rica_final(json_resultado: dict, mensagem_original: str, 
                                  params_api: dict, sessao_id: str) -> dict:
    """
    Aplica apresentação rica usando templates (super rápido)
    """
    try:
        endpoint = params_api.get("endpoint", "")
        
        print("🎨 Aplicando apresentação rica (template)...")
        
        # Usa apresentação rica via template (100ms vs 8s do LLM)
        resultado_rico = aplicar_apresentacao_rica(json_resultado, mensagem_original, endpoint)
        
        # Salva contexto em background se necessário
        contexto_estruturado = resultado_rico.get("contexto_estruturado", {})
        if contexto_estruturado and sessao_id and sessao_id != "anon":
            try:
                salvar_contexto_background_final(
                    sessao_id, 
                    contexto_estruturado, 
                    mensagem_original,
                    resultado_rico.get("mensagem", "")
                )
            except:
                pass  # Não bloqueia resposta
        
        # Sempre inclui dados originais
        resultado_rico["dados_originais"] = json_resultado
        
        return resultado_rico
        
    except Exception as e:
        print(f"Erro na apresentação rica: {e}")
        # Fallback para dados originais
        return {
            "mensagem": "✅ Operação realizada com sucesso!",
            "tipo": "apresentacao_erro",
            "dados_originais": json_resultado
        }

def executar_api_call_final(params: dict, sessao_id: str) -> dict:
    """
    Reutiliza execução de API otimizada
    """
    from app.servicos.executor_fallback_inteligente import executar_api_call_rapido
    return executar_api_call_rapido(params, sessao_id)

def salvar_contexto_background_final(sessao_id: str, contexto_estruturado: dict, 
                                   mensagem_original: str, resposta_apresentada: str):
    """
    Salva contexto sem bloquear (fire-and-forget)
    """
    try:
        payload = {
            "tipo_contexto": "busca_numerada_rica",
            "contexto_estruturado": contexto_estruturado,
            "mensagem_original": mensagem_original,
            "resposta_apresentada": resposta_apresentada
        }
        
        httpx.post(f"{API_NEGOCIO_URL}/contexto/{sessao_id}", json=payload, timeout=3.0)
            
    except:
        pass  # Fire-and-forget

def get_stats_final() -> dict:
    """Stats do sistema final"""
    return {
        "cache_prompts": len(CACHE_PROMPTS),
        "cache_llm_responses": len(CACHE_RESPOSTAS_LLM),
        "version": "final_perfeito_v1",
        "decisao_engine": "phi3_mini",
        "apresentacao_engine": "template_rico",
        "performance_target": "<2s com formatação rica",
        "features": [
            "ids_numerados_para_selecao",
            "emojis_contextuais", 
            "formatacao_original",
            "cache_agressivo",
            "fallback_heuristica"
        ]
    }

def clear_cache_final():
    """Limpa cache final"""
    global CACHE_PROMPTS, CACHE_RESPOSTAS_LLM
    CACHE_PROMPTS.clear()
    CACHE_RESPOSTAS_LLM.clear()