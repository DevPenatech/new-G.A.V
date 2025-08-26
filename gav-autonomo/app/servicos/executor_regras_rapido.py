# gav-autonomo/app/servicos/executor_regras_rapido.py
"""
VERSÃO SIMPLIFICADA - Corrige problemas de import
Otimizações básicas sem complicações
"""

import time
import json
import httpx
import yaml
from typing import Dict, Optional

# Imports que já funcionam
from app.adaptadores.cliente_negocio import obter_prompt_por_nome, listar_exemplos_prompt
from app.adaptadores.interface_llm import completar_para_json
from app.validadores.modelos import validar_json_contra_schema, carregar_schema
from app.config.settings import config

# Cache simples em memória para evitar consultas repetidas
CACHE_PROMPTS = {}
CACHE_TTL = 300  # 5 minutos

API_NEGOCIO_URL = config.API_NEGOCIO_URL.rstrip("/")

def get_prompt_cache_key(nome: str, espaco: str, versao: str) -> str:
    return f"{espaco}:{nome}:v{versao}"

def get_prompt_cached(nome: str, espaco: str = "autonomo", versao: str = "1") -> Optional[dict]:
    """Busca prompt com cache simples"""
    cache_key = get_prompt_cache_key(nome, espaco, versao)
    
    # Verifica cache
    if cache_key in CACHE_PROMPTS:
        entry = CACHE_PROMPTS[cache_key]
        if time.time() - entry["timestamp"] < CACHE_TTL:
            return entry["data"]
    
    # Busca do banco
    try:
        prompt_data = obter_prompt_por_nome(nome, espaco, int(versao))
        exemplos = listar_exemplos_prompt(prompt_data["id"])
        
        resultado = {
            "template": prompt_data["template"],
            "exemplos": exemplos
        }
        
        # Armazena no cache
        CACHE_PROMPTS[cache_key] = {
            "data": resultado,
            "timestamp": time.time()
        }
        
        return resultado
        
    except Exception as e:
        print(f"Erro ao buscar prompt {nome}: {e}")
        return None

def executar_regras_do_manifesto_rapido(mensagem: dict | str) -> dict:
    """
    Versão otimizada simples - apenas com cache de prompts
    """
    start_time = time.time()
    
    if isinstance(mensagem, str):
        mensagem = {"texto": mensagem, "sessao_id": "anon"}
    
    try:
        with open("app/config/model_manifest.yml", encoding="utf-8") as f:
            manifesto = yaml.safe_load(f)
        
        for regra in manifesto["regras"]:
            if regra["action"] == "decisao_llm":
                resultado = processar_decisao_llm_rapido(mensagem, regra, manifesto)
                
                tempo_total = time.time() - start_time
                print(f"⚡ Tempo total: {tempo_total:.2f}s")
                
                # Adiciona métricas na resposta
                if isinstance(resultado, dict):
                    resultado["_performance"] = {
                        "tempo_resposta_ms": round(tempo_total * 1000, 2),
                        "cache_utilizado": len(CACHE_PROMPTS) > 0
                    }
                
                return resultado
    
        return {"erro": "Nenhuma regra válida encontrada no manifesto."}
        
    except Exception as e:
        return {"erro": f"Erro interno: {str(e)}"}

def processar_decisao_llm_rapido(mensagem: dict, regra: dict, manifesto: dict) -> dict:
    """Processamento otimizado com cache"""
    try:
        # 1. Busca prompt do cache (muito mais rápido)
        prompt_data = get_prompt_cached(
            nome=regra["prompt"],
            espaco=regra["espaco_prompt"], 
            versao=str(regra["versao_prompt"])
        )
        
        if not prompt_data:
            return {"erro": "Prompt não encontrado"}
        
        # 2. LLM Selector com timeout reduzido
        print(f"🔄 Consultando LLM... (exemplos: {len(prompt_data['exemplos'])})")
        
        decisao = completar_para_json(
            sistema=prompt_data["template"],
            entrada_usuario=mensagem["texto"],
            exemplos=prompt_data["exemplos"][:3],  # Limita a 3 exemplos para velocidade
            modelo=manifesto["defaults"].get("modelo")
        )
        
        # 3. Validação
        schema = carregar_schema(regra["schema"])
        if not validar_json_contra_schema(decisao, schema):
            return {"erro": "Decisão do LLM inválida", "decisao_recebida": decisao}
        
        # 4. Execução
        tool_name = decisao.get("tool_name")
        
        if tool_name == "api_call":
            return executar_api_call_rapido(decisao.get("parameters", {}), mensagem["sessao_id"])
            
        elif tool_name == "api_call_with_presentation":
            # Executa API primeiro
            json_resultado = executar_api_call_rapido(decisao.get("parameters", {}), mensagem["sessao_id"])
            
            # Tenta apresentação (se falhar, retorna JSON)
            try:
                return apresentar_resultado_rapido(
                    json_resultado, 
                    mensagem["texto"], 
                    decisao.get("parameters", {})
                )
            except Exception as e:
                print(f"Erro na apresentação: {e}")
                return json_resultado
                
        else:
            return {"erro": f"Ferramenta não reconhecida: {tool_name}"}
            
    except Exception as e:
        print(f"Erro no processamento: {e}")
        return {"erro": f"Erro interno: {str(e)}"}

def executar_api_call_rapido(params: dict, sessao_id: str) -> dict:
    """Execução de API call com timeout reduzido"""
    endpoint = params.get("endpoint", "")
    method = params.get("method", "GET").upper()
    body = params.get("body", {})
    
    # Endpoints especiais
    if endpoint == "/chat/resposta":
        mensagem = body.get("mensagem", "Olá! Como posso ajudá-lo?")
        return {"mensagem": mensagem, "tipo": "conversacional"}
    
    if endpoint == "/chat/contexto":
        return processar_contexto_rapido(body, sessao_id)
    
    # APIs reais
    if "{sessao_id}" in endpoint:
        if not sessao_id or sessao_id == "anon":
            return {"erro": "Sessão necessária para esta operação."}
        endpoint = endpoint.replace("{sessao_id}", sessao_id)
    
    url = f"{API_NEGOCIO_URL}{endpoint}"
    
    try:
        # Timeout reduzido para 10 segundos
        if method == "GET":
            resp = httpx.get(url, timeout=10.0)
        elif method == "POST":
            resp = httpx.post(url, json=body, timeout=10.0)
        elif method == "PUT":
            resp = httpx.put(url, json=body, timeout=10.0)
        elif method == "DELETE":
            resp = httpx.delete(url, timeout=10.0)
        else:
            return {"erro": f"Método HTTP não suportado: {method}"}
        
        if resp.is_success:
            return resp.json()
        else:
            return {"erro": f"API retornou erro {resp.status_code}", "detalhe": resp.text[:500]}
            
    except httpx.TimeoutException:
        return {"erro": "Timeout na comunicação com API (10s)"}
    except Exception as e:
        return {"erro": f"Falha na comunicação: {str(e)}"}

def apresentar_resultado_rapido(json_resultado: dict, mensagem_original: str, params_api: dict) -> dict:
    """Apresentação rápida do resultado"""
    try:
        endpoint = params_api.get("endpoint", "")
        prompt_apresentador = determinar_prompt_apresentador(endpoint, json_resultado)
        
        if not prompt_apresentador:
            return json_resultado
        
        # Busca prompt do apresentador (com cache)
        prompt_data = get_prompt_cached(prompt_apresentador, "autonomo", "1")
        
        if not prompt_data:
            return json_resultado
        
        contexto_apresentacao = montar_contexto_apresentacao(
            mensagem_original, json_resultado, endpoint
        )
        
        # LLM Apresentador com timeout reduzido
        resposta_conversacional = completar_para_json(
            sistema=prompt_data["template"],
            entrada_usuario=contexto_apresentacao,
            exemplos=prompt_data["exemplos"][:2]  # Apenas 2 exemplos para velocidade
        )
        
        # Salva contexto em background se necessário
        sessao_id = params_api.get("sessao_id")
        if sessao_id and sessao_id != "anon":
            contexto_estruturado = resposta_conversacional.get("contexto_estruturado", {})
            if contexto_estruturado and contexto_estruturado.get("produtos"):
                salvar_contexto_background(
                    sessao_id, contexto_estruturado, mensagem_original,
                    resposta_conversacional.get("mensagem", "")
                )
        
        return {
            "mensagem": resposta_conversacional.get("mensagem", "Ops, não consegui processar isso..."),
            "tipo": resposta_conversacional.get("tipo", "apresentacao"),
            "dados_originais": json_resultado
        }
        
    except Exception as e:
        print(f"Erro na apresentação: {e}")
        return json_resultado

def processar_contexto_rapido(body: dict, sessao_id: str) -> dict:
    """Processamento rápido de contexto com regex simples"""
    try:
        mensagem_contexto = body.get("mensagem_contexto", "")
        
        # Busca contexto do banco (sem cache por agora)
        contexto_banco = buscar_contexto_do_banco_rapido(sessao_id)
        
        # Processamento por ID direto
        import re
        id_matches = re.findall(r'\b(\d{4,6})\b', mensagem_contexto)
        
        if id_matches and contexto_banco:
            item_id_referenciado = int(id_matches[0])
            quantidade_match = re.search(r'(\d+)\s*(unidades?|do|da|vezes?)', mensagem_contexto)
            quantidade = int(quantidade_match.group(1)) if quantidade_match else 1
            
            produtos = contexto_banco.get("contexto_estruturado", {}).get("produtos", [])
            produto_encontrado = next((p for p in produtos if p.get("item_id") == item_id_referenciado), None)
            
            if produto_encontrado:
                return executar_api_call_rapido({
                    "endpoint": "/carrinhos/{sessao_id}/itens",
                    "method": "POST",
                    "body": {
                        "item_id": item_id_referenciado,
                        "quantidade": quantidade,
                        "codfilial": 2
                    }
                }, sessao_id)
        
        return {"erro": "Contexto não encontrado ou ID inválido"}
        
    except Exception as e:
        return {"erro": f"Erro no processamento: {str(e)}"}

def buscar_contexto_do_banco_rapido(sessao_id: str) -> Optional[dict]:
    """Busca rápida de contexto"""
    try:
        response = httpx.get(f"{API_NEGOCIO_URL}/contexto/{sessao_id}", timeout=5.0)
        return response.json() if response.is_success else None
    except:
        return None

def salvar_contexto_background(sessao_id: str, contexto_estruturado: dict, 
                              mensagem_original: str, resposta_apresentada: str):
    """Salva contexto sem bloquear (versão simples)"""
    try:
        payload = {
            "tipo_contexto": "busca_numerada",
            "contexto_estruturado": contexto_estruturado,
            "mensagem_original": mensagem_original,
            "resposta_apresentada": resposta_apresentada
        }
        
        # Salva em background (ignora erros)
        httpx.post(f"{API_NEGOCIO_URL}/contexto/{sessao_id}", json=payload, timeout=5.0)
            
    except:
        pass  # Ignora erros para não quebrar a resposta

def determinar_prompt_apresentador(endpoint: str, json_resultado: dict) -> Optional[str]:
    """Determina qual prompt usar baseado no endpoint"""
    if "erro" in json_resultado:
        return "prompt_apresentador_erro"
    if "/produtos/busca" in endpoint:
        return "prompt_apresentador_busca"
    if "/carrinhos/" in endpoint:
        return "prompt_apresentador_carrinho"
    return None

def montar_contexto_apresentacao(mensagem_original: str, json_resultado: dict, endpoint: str) -> str:
    """Monta contexto para o apresentador"""
    if "/produtos/busca" in endpoint:
        resultados = json_resultado.get("resultados", [])
        status_busca = json_resultado.get("status_busca", "sucesso")
        
        return f"""query_original: "{mensagem_original}"
resultados_json: {json.dumps(json_resultado, ensure_ascii=False)}
status_busca: "{status_busca}"
total_encontrados: {len(resultados)}"""

    elif "/carrinhos/" in endpoint:
        if endpoint.endswith("/itens"):
            acao = "item_adicionado"
        else:
            acao = "carrinho_visualizado" if json_resultado.get("itens") else "carrinho_vazio"
            
        return f"""acao_realizada: "{acao}"
carrinho_json: {json.dumps(json_resultado, ensure_ascii=False)}
mensagem_original: "{mensagem_original}" """

    else:
        return f"""contexto_usuario: "{mensagem_original}"
resultado_api: {json.dumps(json_resultado, ensure_ascii=False)}
endpoint: "{endpoint}" """

# Status do cache para debugging
def get_cache_stats() -> dict:
    return {
        "cache_size": len(CACHE_PROMPTS),
        "cached_prompts": list(CACHE_PROMPTS.keys())
    }