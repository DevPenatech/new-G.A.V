# gav-autonomo/app/servicos/executor_fallback_inteligente.py
"""
FASE 3: Fallback Inteligente para LLM Lento
- Se LLM falhar, usa respostas template
- Apresentação simplificada sem LLM quando necessário
- Timeout escalonado (5s primeiro, 10s backup)
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

# Reutiliza cache da versão anterior
from app.servicos.executor_super_rapido import (
    CACHE_PROMPTS, CACHE_RESPOSTAS_LLM, CACHE_TTL, MAX_EXEMPLOS,
    hash_prompt, get_prompt_cached_super
)

API_NEGOCIO_URL = config.API_NEGOCIO_URL.rstrip("/")

# Templates de fallback para quando o LLM falhar
FALLBACK_APRESENTACAO = {
    "busca_produtos": {
        "mensagem": "Encontrei {total} produtos para '{query}'. Vou listar as principais opções: {lista_produtos}",
        "tipo": "busca_fallback"
    },
    "carrinho_vazio": {
        "mensagem": "Seu carrinho está vazio! 🛒 Que tal adicionar alguns produtos?",
        "tipo": "carrinho_fallback"
    },
    "carrinho_itens": {
        "mensagem": "Seu carrinho tem {total_itens} itens no valor total de R$ {valor_total:.2f}",
        "tipo": "carrinho_fallback"
    },
    "item_adicionado": {
        "mensagem": "✅ Item adicionado ao carrinho com sucesso!",
        "tipo": "carrinho_fallback"
    },
    "erro_geral": {
        "mensagem": "Desculpe, houve um problema. Tente novamente ou reformule sua pergunta.",
        "tipo": "erro_fallback"
    }
}

def completar_para_json_com_fallback(template_compilado: str, entrada_usuario: str, 
                                    cache_hash: str, timeout_primario: int = 5) -> dict:
    """LLM com fallback escalonado"""
    
    # Verifica cache primeiro
    if cache_hash in CACHE_RESPOSTAS_LLM:
        entry = CACHE_RESPOSTAS_LLM[cache_hash]
        if time.time() - entry["timestamp"] < CACHE_TTL:
            print("⚡ Cache HIT - resposta LLM reutilizada!")
            return entry["resposta"]
    
    prompt_final = template_compilado.replace("{ENTRADA_USUARIO}", entrada_usuario)
    
    # Tentativa 1: Timeout agressivo (5s)
    print(f"🤖 Tentativa 1: LLM (timeout: {timeout_primario}s)...")
    resultado = tentar_llm_com_timeout(prompt_final, timeout_primario)
    
    if resultado and "erro" not in resultado:
        # Sucesso - armazena no cache
        CACHE_RESPOSTAS_LLM[cache_hash] = {
            "resposta": resultado,
            "timestamp": time.time()
        }
        return resultado
    
    # Tentativa 2: Timeout mais longo (10s)
    print(f"🔄 Tentativa 2: LLM (timeout: 10s)...")
    resultado = tentar_llm_com_timeout(prompt_final, 10)
    
    if resultado and "erro" not in resultado:
        CACHE_RESPOSTAS_LLM[cache_hash] = {
            "resposta": resultado,
            "timestamp": time.time()
        }
        return resultado
    
    # Falha total - retorna erro estruturado
    print("❌ LLM falhou completamente - usando fallback")
    return {"erro": "llm_failed", "fallback_needed": True}

def tentar_llm_com_timeout(prompt: str, timeout: int) -> Optional[dict]:
    """Tenta uma chamada LLM com timeout específico"""
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{config.OLLAMA_HOST}/api/generate",
                json={
                    "model": config.OLLAMA_MODEL_NAME,
                    "prompt": prompt,
                    "format": "json",
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "top_p": 0.9,
                        "num_predict": 200,  # Ainda mais reduzido
                        "stop": ["\n\n", "```", "---", "Output:", "Resposta:"]
                    }
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                conteudo = data.get("response", "").strip()
                
                try:
                    return json.loads(conteudo)
                except json.JSONDecodeError:
                    # Tenta extrair JSON
                    import re
                    json_match = re.search(r'\{.*\}', conteudo, re.DOTALL)
                    if json_match:
                        try:
                            return json.loads(json_match.group())
                        except:
                            pass
                    return None
    
    except (httpx.TimeoutException, Exception):
        return None

def executar_regras_com_fallback(mensagem: dict | str) -> dict:
    """Executor com fallback inteligente"""
    start_time = time.time()
    
    if isinstance(mensagem, str):
        mensagem = {"texto": mensagem, "sessao_id": "anon"}
    
    try:
        with open("app/config/model_manifest.yml", encoding="utf-8") as f:
            manifesto = yaml.safe_load(f)
        
        for regra in manifesto["regras"]:
            if regra["action"] == "decisao_llm":
                resultado = processar_decisao_com_fallback(mensagem, regra, manifesto)
                
                tempo_total = time.time() - start_time
                print(f"⚡ Tempo com FALLBACK: {tempo_total:.2f}s")
                
                if isinstance(resultado, dict):
                    resultado["_performance"] = {
                        "tempo_resposta_ms": round(tempo_total * 1000, 2),
                        "cache_size": len(CACHE_PROMPTS),
                        "llm_cache_size": len(CACHE_RESPOSTAS_LLM),
                        "versao": "fallback_inteligente_v1"
                    }
                
                return resultado
    
        return {"erro": "Nenhuma regra válida encontrada no manifesto."}
        
    except Exception as e:
        return {"erro": f"Erro interno: {str(e)}"}

def processar_decisao_com_fallback(mensagem: dict, regra: dict, manifesto: dict) -> dict:
    """Processamento com fallback para LLM Selector"""
    try:
        # 1. Busca prompt do cache
        prompt_data = get_prompt_cached_super(
            nome=regra["prompt"],
            espaco=regra["espaco_prompt"], 
            versao=str(regra["versao_prompt"])
        )
        
        if not prompt_data:
            return {"erro": "Prompt não encontrado"}
        
        # 2. LLM Selector com fallback
        entrada_usuario = mensagem["texto"]
        cache_hash = hash_prompt(
            prompt_data["template"], 
            entrada_usuario, 
            len(prompt_data["exemplos"])
        )
        
        decisao = completar_para_json_com_fallback(
            prompt_data["template_otimizado"], 
            entrada_usuario, 
            cache_hash,
            timeout_primario=5
        )
        
        # 3. Se LLM falhou, usa heurística simples
        if decisao.get("erro") == "llm_failed" or decisao.get("fallback_needed"):
            print("🎯 LLM Selector falhou - usando heurística")
            decisao = decidir_por_heuristica(entrada_usuario)
        
        # 4. Validação
        if "erro" in decisao and not decisao.get("fallback_needed"):
            return decisao
            
        schema = carregar_schema(regra["schema"])
        if not validar_json_contra_schema(decisao, schema):
            # Se validação falhou, tenta heurística também
            print("🎯 Validação falhou - usando heurística")
            decisao = decidir_por_heuristica(entrada_usuario)
        
        # 5. Execução
        tool_name = decisao.get("tool_name")
        
        if tool_name == "api_call":
            return executar_api_call_rapido(decisao.get("parameters", {}), mensagem["sessao_id"])
            
        elif tool_name == "api_call_with_presentation":
            # API primeiro
            json_resultado = executar_api_call_rapido(decisao.get("parameters", {}), mensagem["sessao_id"])
            
            # Apresentação com fallback template
            return apresentar_com_fallback(
                json_resultado, 
                mensagem["texto"], 
                decisao.get("parameters", {})
            )
                
        else:
            return {"erro": f"Ferramenta não reconhecida: {tool_name}"}
            
    except Exception as e:
        print(f"Erro no processamento: {e}")
        return {"erro": f"Erro interno: {str(e)}"}

def decidir_por_heuristica(entrada_usuario: str) -> dict:
    """Heurística simples quando LLM falha"""
    entrada_lower = entrada_usuario.lower()
    
    # Padrões de busca
    if any(palavra in entrada_lower for palavra in ["buscar", "procurar", "quero", "tem"]):
        # Remove palavras de comando para extrair produto
        query = entrada_usuario
        for palavra in ["buscar", "procurar", "quero", "tem", "por"]:
            query = query.replace(palavra, "").strip()
        
        return {
            "tool_name": "api_call_with_presentation",
            "parameters": {
                "endpoint": "/produtos/busca",
                "method": "POST",
                "body": {"query": query, "limit": 10, "codfilial": 2}
            }
        }
    
    # Padrões de carrinho
    if any(palavra in entrada_lower for palavra in ["carrinho", "sacola"]):
        return {
            "tool_name": "api_call_with_presentation",
            "parameters": {
                "endpoint": "/carrinhos/{sessao_id}",
                "method": "GET",
                "body": {}
            }
        }
    
    # Conversa genérica
    return {
        "tool_name": "api_call",
        "parameters": {
            "endpoint": "/chat/resposta",
            "method": "POST",
            "body": {"mensagem": "Olá! Posso te ajudar a buscar produtos ou ver seu carrinho. O que você precisa?"}
        }
    }

def apresentar_com_fallback(json_resultado: dict, mensagem_original: str, params_api: dict) -> dict:
    """Apresentação com fallback para templates simples"""
    try:
        endpoint = params_api.get("endpoint", "")
        
        # 1. Tenta apresentação com LLM primeiro
        if "/produtos/busca" in endpoint:
            prompt_data = get_prompt_cached_super("prompt_apresentador_busca", "autonomo", "1")
            
            if prompt_data:
                contexto = montar_contexto_apresentacao(mensagem_original, json_resultado, endpoint)
                cache_hash = hash_prompt(prompt_data["template"], contexto, len(prompt_data["exemplos"]))
                
                resposta_llm = completar_para_json_com_fallback(
                    prompt_data["template_otimizado"],
                    contexto,
                    cache_hash,
                    timeout_primario=4  # Ainda mais agressivo para apresentação
                )
                
                # Se LLM funcionou, usa resultado
                if "erro" not in resposta_llm and resposta_llm.get("mensagem"):
                    return {
                        "mensagem": resposta_llm["mensagem"],
                        "tipo": resposta_llm.get("tipo", "apresentacao_llm"),
                        "dados_originais": json_resultado
                    }
        
        # 2. Fallback para template simples
        print("🎯 Usando template de fallback para apresentação")
        return usar_template_fallback(json_resultado, mensagem_original, endpoint)
        
    except Exception as e:
        print(f"Erro na apresentação: {e}")
        return usar_template_fallback(json_resultado, mensagem_original, endpoint)

def usar_template_fallback(json_resultado: dict, mensagem_original: str, endpoint: str) -> dict:
    """Usa templates simples quando LLM falha"""
    
    if "erro" in json_resultado:
        template = FALLBACK_APRESENTACAO["erro_geral"]
        return {
            "mensagem": template["mensagem"],
            "tipo": template["tipo"],
            "dados_originais": json_resultado
        }
    
    if "/produtos/busca" in endpoint:
        resultados = json_resultado.get("resultados", [])
        
        if not resultados:
            return {
                "mensagem": f"Não encontrei produtos para '{mensagem_original}'. Tente outro termo de busca.",
                "tipo": "busca_vazia",
                "dados_originais": json_resultado
            }
        
        # Cria lista simplificada
        lista_produtos = []
        for i, produto in enumerate(resultados[:3]):  # Máximo 3
            nome = produto.get("descricaoweb", produto.get("descricao", "Produto"))
            primeiro_item = produto.get("itens", [{}])[0]
            preco = primeiro_item.get("poferta") or primeiro_item.get("pvenda")
            
            if preco:
                lista_produtos.append(f"{i+1}. {nome} - R$ {preco:.2f}")
            else:
                lista_produtos.append(f"{i+1}. {nome}")
        
        template = FALLBACK_APRESENTACAO["busca_produtos"]
        mensagem = template["mensagem"].format(
            total=len(resultados),
            query=mensagem_original,
            lista_produtos="; ".join(lista_produtos)
        )
        
        return {
            "mensagem": mensagem,
            "tipo": template["tipo"],
            "dados_originais": json_resultado
        }
    
    elif "/carrinhos/" in endpoint:
        if endpoint.endswith("/itens"):
            template = FALLBACK_APRESENTACAO["item_adicionado"]
        elif json_resultado.get("itens"):
            itens = json_resultado.get("itens", [])
            valor_total = json_resultado.get("valor_total", 0)
            
            template = FALLBACK_APRESENTACAO["carrinho_itens"]
            mensagem = template["mensagem"].format(
                total_itens=len(itens),
                valor_total=valor_total
            )
            
            return {
                "mensagem": mensagem,
                "tipo": template["tipo"],
                "dados_originais": json_resultado
            }
        else:
            template = FALLBACK_APRESENTACAO["carrinho_vazio"]
        
        return {
            "mensagem": template["mensagem"],
            "tipo": template["tipo"],
            "dados_originais": json_resultado
        }
    
    # Fallback genérico
    return {
        "mensagem": "Operação realizada com sucesso!",
        "tipo": "sucesso_generico",
        "dados_originais": json_resultado
    }

# Reutiliza funções que já funcionam
def executar_api_call_rapido(params: dict, sessao_id: str) -> dict:
    """Reutiliza da versão anterior"""
    from app.servicos.executor_super_rapido import executar_api_call_rapido as exec_original
    return exec_original(params, sessao_id)

def montar_contexto_apresentacao(mensagem_original: str, json_resultado: dict, endpoint: str) -> str:
    """Reutiliza da versão anterior"""
    from app.servicos.executor_super_rapido import montar_contexto_apresentacao as montar_original
    return montar_original(mensagem_original, json_resultado, endpoint)

def get_fallback_stats() -> dict:
    """Stats do sistema com fallback"""
    return {
        "cache_prompts": len(CACHE_PROMPTS),
        "cache_llm_responses": len(CACHE_RESPOSTAS_LLM),
        "fallback_templates": list(FALLBACK_APRESENTACAO.keys()),
        "version": "fallback_inteligente_v1",
        "timeouts": "5s + 10s backup",
        "heuristica_ativa": True
    }