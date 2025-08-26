# gav-autonomo/app/servicos/executor_super_rapido.py
"""
FASE 2: Otimizações Agressivas
- Máximo 2 exemplos por prompt
- Cache persistente entre chamadas  
- Timeout agressivo no LLM (8s)
- Compilação de prompts otimizada
"""

import time
import json
import httpx
import yaml
import hashlib
from typing import Dict, Optional

# Imports existentes
from app.adaptadores.cliente_negocio import obter_prompt_por_nome, listar_exemplos_prompt
from app.adaptadores.interface_llm import completar_para_json
from app.validadores.modelos import validar_json_contra_schema, carregar_schema
from app.config.settings import config

# Cache global persistente e otimizado
CACHE_PROMPTS = {}
CACHE_RESPOSTAS_LLM = {}  # Cache de respostas LLM por hash do prompt
CACHE_TTL = 600  # 10 minutos (mais longo)
MAX_EXEMPLOS = 2  # MÁXIMO 2 exemplos para velocidade extrema
LLM_TIMEOUT_AGRESSIVO = 8  # 8 segundos máximo

API_NEGOCIO_URL = config.API_NEGOCIO_URL.rstrip("/")

def hash_prompt(sistema: str, entrada: str, exemplos_count: int) -> str:
    """Cria hash único para cache de respostas LLM"""
    content = f"{sistema[:200]}{entrada}{exemplos_count}"
    return hashlib.md5(content.encode()).hexdigest()[:16]

def get_prompt_cached_super(nome: str, espaco: str = "autonomo", versao: str = "1") -> Optional[dict]:
    """Cache super otimizado com exemplos limitados"""
    cache_key = f"{espaco}:{nome}:v{versao}"
    
    # Verifica cache
    if cache_key in CACHE_PROMPTS:
        entry = CACHE_PROMPTS[cache_key]
        if time.time() - entry["timestamp"] < CACHE_TTL:
            print(f"✅ Cache HIT para {nome}")
            return entry["data"]
        else:
            # Remove entrada expirada
            del CACHE_PROMPTS[cache_key]
    
    # Busca do banco
    print(f"🔄 Cache MISS para {nome} - buscando...")
    try:
        prompt_data = obter_prompt_por_nome(nome, espaco, int(versao))
        exemplos_completos = listar_exemplos_prompt(prompt_data["id"])
        
        # 🚀 OTIMIZAÇÃO CRÍTICA: Limita exemplos drasticamente
        exemplos_limitados = exemplos_completos[:MAX_EXEMPLOS]
        
        print(f"⚡ Exemplos limitados: {len(exemplos_completos)} → {len(exemplos_limitados)}")
        
        resultado = {
            "template": prompt_data["template"],
            "exemplos": exemplos_limitados,
            "template_otimizado": _compilar_template_otimizado(prompt_data["template"], exemplos_limitados)
        }
        
        # Armazena no cache
        CACHE_PROMPTS[cache_key] = {
            "data": resultado,
            "timestamp": time.time()
        }
        
        return resultado
        
    except Exception as e:
        print(f"❌ Erro ao buscar prompt {nome}: {e}")
        return None

def _compilar_template_otimizado(template: str, exemplos: list) -> str:
    """Pré-compila template com exemplos para reutilização"""
    partes = [template.strip()]
    
    # Adiciona exemplos de forma compacta
    for i, ex in enumerate(exemplos):
        input_ex = ex.get("exemplo_input", "").strip()
        output_ex = ex.get("exemplo_output_json", "").strip()
        
        if input_ex and output_ex:
            partes.append(f"Ex{i+1}: {input_ex} → {output_ex}")
    
    return "\n\n".join(partes) + "\n\nEntrada: {ENTRADA_USUARIO}"

def completar_para_json_super_rapido(template_compilado: str, entrada_usuario: str, cache_hash: str) -> dict:
    """LLM com cache de respostas e timeout agressivo"""
    
    # Verifica cache de respostas LLM
    if cache_hash in CACHE_RESPOSTAS_LLM:
        entry = CACHE_RESPOSTAS_LLM[cache_hash]
        if time.time() - entry["timestamp"] < CACHE_TTL:
            print("⚡ Cache HIT - resposta LLM reutilizada!")
            return entry["resposta"]
    
    # Monta prompt final
    prompt_final = template_compilado.replace("{ENTRADA_USUARIO}", entrada_usuario)
    
    print(f"🤖 Chamando LLM (timeout: {LLM_TIMEOUT_AGRESSIVO}s)...")
    
    try:
        # Usa httpx diretamente com timeout agressivo
        with httpx.Client(timeout=LLM_TIMEOUT_AGRESSIVO) as client:
            response = client.post(
                f"{config.OLLAMA_HOST}/api/generate",
                json={
                    "model": config.OLLAMA_MODEL_NAME,
                    "prompt": prompt_final,
                    "format": "json",
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "top_p": 0.9,
                        "num_predict": 300,  # Reduzido drasticamente
                        "stop": ["\n\n", "```", "---"]  # Para mais cedo
                    }
                }
            )
            
            if response.status_code != 200:
                raise Exception(f"Ollama retornou {response.status_code}")
            
            data = response.json()
            conteudo = data.get("response", "").strip()
            
            # Parse JSON mais robusto
            try:
                resultado = json.loads(conteudo)
                
                # Armazena no cache de respostas
                CACHE_RESPOSTAS_LLM[cache_hash] = {
                    "resposta": resultado,
                    "timestamp": time.time()
                }
                
                return resultado
                
            except json.JSONDecodeError:
                # Fallback: tenta extrair JSON
                import re
                json_match = re.search(r'\{.*\}', conteudo, re.DOTALL)
                if json_match:
                    try:
                        resultado = json.loads(json_match.group())
                        return resultado
                    except:
                        pass
                
                print(f"⚠️ JSON inválido do LLM: {conteudo[:100]}...")
                return {"erro": "json_invalido", "conteudo_bruto": conteudo[:200]}
    
    except httpx.TimeoutException:
        print(f"⏱️ LLM timeout após {LLM_TIMEOUT_AGRESSIVO}s")
        return {"erro": "llm_timeout", "timeout": LLM_TIMEOUT_AGRESSIVO}
    except Exception as e:
        print(f"❌ Erro LLM: {e}")
        return {"erro": "llm_error", "detalhe": str(e)}

def executar_regras_super_rapido(mensagem: dict | str) -> dict:
    """
    Executor SUPER otimizado - Fase 2
    Meta: <5s por consulta
    """
    start_time = time.time()
    
    if isinstance(mensagem, str):
        mensagem = {"texto": mensagem, "sessao_id": "anon"}
    
    try:
        with open("app/config/model_manifest.yml", encoding="utf-8") as f:
            manifesto = yaml.safe_load(f)
        
        for regra in manifesto["regras"]:
            if regra["action"] == "decisao_llm":
                resultado = processar_decisao_super_rapido(mensagem, regra, manifesto)
                
                tempo_total = time.time() - start_time
                print(f"⚡ Tempo SUPER: {tempo_total:.2f}s")
                
                if isinstance(resultado, dict):
                    resultado["_performance"] = {
                        "tempo_resposta_ms": round(tempo_total * 1000, 2),
                        "cache_size": len(CACHE_PROMPTS),
                        "llm_cache_size": len(CACHE_RESPOSTAS_LLM),
                        "versao": "super_rapido_v2"
                    }
                
                return resultado
    
        return {"erro": "Nenhuma regra válida encontrada no manifesto."}
        
    except Exception as e:
        return {"erro": f"Erro interno: {str(e)}"}

def processar_decisao_super_rapido(mensagem: dict, regra: dict, manifesto: dict) -> dict:
    """Processamento com todas as otimizações"""
    try:
        # 1. Busca prompt do cache (super otimizado)
        prompt_data = get_prompt_cached_super(
            nome=regra["prompt"],
            espaco=regra["espaco_prompt"], 
            versao=str(regra["versao_prompt"])
        )
        
        if not prompt_data:
            return {"erro": "Prompt não encontrado"}
        
        # 2. LLM Selector com cache de resposta
        entrada_usuario = mensagem["texto"]
        cache_hash = hash_prompt(
            prompt_data["template"], 
            entrada_usuario, 
            len(prompt_data["exemplos"])
        )
        
        decisao = completar_para_json_super_rapido(
            prompt_data["template_otimizado"], 
            entrada_usuario, 
            cache_hash
        )
        
        # 3. Validação rápida
        if "erro" in decisao:
            return decisao
            
        schema = carregar_schema(regra["schema"])
        if not validar_json_contra_schema(decisao, schema):
            return {"erro": "Decisão inválida", "decisao": decisao}
        
        # 4. Execução
        tool_name = decisao.get("tool_name")
        
        if tool_name == "api_call":
            return executar_api_call_rapido(decisao.get("parameters", {}), mensagem["sessao_id"])
            
        elif tool_name == "api_call_with_presentation":
            # API primeiro
            json_resultado = executar_api_call_rapido(decisao.get("parameters", {}), mensagem["sessao_id"])
            
            # Apresentação com cache também
            try:
                return apresentar_resultado_super_rapido(
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

def apresentar_resultado_super_rapido(json_resultado: dict, mensagem_original: str, params_api: dict) -> dict:
    """Apresentação com cache de LLM"""
    try:
        endpoint = params_api.get("endpoint", "")
        prompt_apresentador = determinar_prompt_apresentador(endpoint, json_resultado)
        
        if not prompt_apresentador:
            return json_resultado
        
        # Busca prompt do apresentador (com cache)
        prompt_data = get_prompt_cached_super(prompt_apresentador, "autonomo", "1")
        
        if not prompt_data:
            return json_resultado
        
        contexto_apresentacao = montar_contexto_apresentacao(
            mensagem_original, json_resultado, endpoint
        )
        
        # Cache para apresentação também
        cache_hash = hash_prompt(
            prompt_data["template"], 
            contexto_apresentacao, 
            len(prompt_data["exemplos"])
        )
        
        resposta_conversacional = completar_para_json_super_rapido(
            prompt_data["template_otimizado"],
            contexto_apresentacao,
            cache_hash
        )
        
        # Salva contexto em background (não bloqueia)
        sessao_id = params_api.get("sessao_id")
        if sessao_id and sessao_id != "anon":
            contexto_estruturado = resposta_conversacional.get("contexto_estruturado", {})
            if contexto_estruturado and contexto_estruturado.get("produtos"):
                try:
                    salvar_contexto_background_rapido(
                        sessao_id, contexto_estruturado, mensagem_original,
                        resposta_conversacional.get("mensagem", "")
                    )
                except:
                    pass  # Não bloqueia resposta se falhar
        
        return {
            "mensagem": resposta_conversacional.get("mensagem", "Ops, não consegui processar isso..."),
            "tipo": resposta_conversacional.get("tipo", "apresentacao"),
            "dados_originais": json_resultado
        }
        
    except Exception as e:
        print(f"Erro na apresentação: {e}")
        return json_resultado

# Reutiliza funções da versão anterior que já funcionam
def executar_api_call_rapido(params: dict, sessao_id: str) -> dict:
    """Reutiliza implementação anterior"""
    from app.servicos.executor_regras_rapido import executar_api_call_rapido as exec_api_original
    return exec_api_original(params, sessao_id)

def determinar_prompt_apresentador(endpoint: str, json_resultado: dict) -> Optional[str]:
    """Reutiliza implementação anterior"""
    if "erro" in json_resultado:
        return "prompt_apresentador_erro"
    if "/produtos/busca" in endpoint:
        return "prompt_apresentador_busca"
    if "/carrinhos/" in endpoint:
        return "prompt_apresentador_carrinho"
    return None

def montar_contexto_apresentacao(mensagem_original: str, json_resultado: dict, endpoint: str) -> str:
    """Reutiliza implementação anterior"""
    from app.servicos.executor_regras_rapido import montar_contexto_apresentacao as montar_original
    return montar_original(mensagem_original, json_resultado, endpoint)

def salvar_contexto_background_rapido(sessao_id: str, contexto_estruturado: dict, 
                                    mensagem_original: str, resposta_apresentada: str):
    """Salva contexto ultra-rápido"""
    try:
        payload = {
            "tipo_contexto": "busca_numerada",
            "contexto_estruturado": contexto_estruturado,
            "mensagem_original": mensagem_original,
            "resposta_apresentada": resposta_apresentada
        }
        
        # Fire-and-forget com timeout baixo
        httpx.post(f"{API_NEGOCIO_URL}/contexto/{sessao_id}", json=payload, timeout=2.0)
            
    except:
        pass  # Ignora completamente

def get_super_cache_stats() -> dict:
    """Stats do cache avançado"""
    return {
        "cache_prompts": len(CACHE_PROMPTS),
        "cache_llm_responses": len(CACHE_RESPOSTAS_LLM),
        "max_exemplos": MAX_EXEMPLOS,
        "llm_timeout": LLM_TIMEOUT_AGRESSIVO,
        "cached_prompts": list(CACHE_PROMPTS.keys()),
        "version": "super_rapido_v2"
    }

def clear_super_cache():
    """Limpa todos os caches"""
    global CACHE_PROMPTS, CACHE_RESPOSTAS_LLM
    CACHE_PROMPTS.clear()
    CACHE_RESPOSTAS_LLM.clear()