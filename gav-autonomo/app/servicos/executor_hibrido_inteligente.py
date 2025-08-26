# gav-autonomo/app/servicos/executor_hibrido_inteligente.py
"""
Executor Híbrido Inteligente:
- PHI3:mini para decisões (0.04s)  
- Qwen2:7b SELETIVO para apresentação rica (3s apenas quando necessário)
- Templates como fallback para casos simples
- Performance adaptativa baseada na complexidade
"""

import time
import httpx
import yaml
import json
from typing import Dict, Optional

from app.adaptadores.cliente_negocio import obter_prompt_por_nome, listar_exemplos_prompt
from app.validadores.modelos import validar_json_contra_schema, carregar_schema
from app.config.settings import config

# Reutiliza cache
from app.servicos.executor_fallback_inteligente import (
    CACHE_PROMPTS, CACHE_RESPOSTAS_LLM, CACHE_TTL,
    hash_prompt, get_prompt_cached_super, decidir_por_heuristica
)

API_NEGOCIO_URL = config.API_NEGOCIO_URL.rstrip("/")

# Configuração de modelos
MODELO_DECISAO = "phi3:mini"      # Rápido para decisões
MODELO_APRESENTACAO = "qwen2:7b"   # Rico para apresentação

def executar_regras_hibrido_inteligente(mensagem: dict | str) -> dict:
    """
    Executor híbrido que usa o modelo mais adequado para cada tarefa
    """
    start_time = time.time()
    
    if isinstance(mensagem, str):
        mensagem = {"texto": mensagem, "sessao_id": "anon"}
    
    try:
        with open("app/config/model_manifest.yml", encoding="utf-8") as f:
            manifesto = yaml.safe_load(f)
        
        for regra in manifesto["regras"]:
            if regra["action"] == "decisao_llm":
                resultado = processar_decisao_hibrida(mensagem, regra, manifesto)
                
                tempo_total = time.time() - start_time
                print(f"🔥 Tempo HÍBRIDO: {tempo_total:.2f}s")
                
                if isinstance(resultado, dict):
                    resultado["_performance"] = {
                        "tempo_resposta_ms": round(tempo_total * 1000, 2),
                        "versao": "hibrido_inteligente_v1",
                        "modelo_decisao": MODELO_DECISAO,
                        "modelo_apresentacao": MODELO_APRESENTACAO if resultado.get("usou_llm_apresentacao") else "template"
                    }
                
                return resultado
    
        return {"erro": "Nenhuma regra válida encontrada no manifesto."}
        
    except Exception as e:
        return {"erro": f"Erro interno: {str(e)}"}

def processar_decisao_hibrida(mensagem: dict, regra: dict, manifesto: dict) -> dict:
    """
    Processamento híbrido: PHI3 para decisão, Qwen2 seletivo para apresentação
    """
    try:
        # 1. FASE DECISÃO: PHI3:mini (rápido)
        print("🚀 Fase 1: Decisão com PHI3:mini...")
        
        prompt_data = get_prompt_cached_super(
            nome=regra["prompt"],
            espaco=regra["espaco_prompt"], 
            versao=str(regra["versao_prompt"])
        )
        
        if not prompt_data:
            return {"erro": "Prompt não encontrado"}
        
        # Decisão com PHI3
        entrada_usuario = mensagem["texto"]
        cache_hash = hash_prompt(prompt_data["template"], entrada_usuario, len(prompt_data["exemplos"]))
        
        decisao = completar_com_modelo_especifico(
            prompt_data["template_otimizado"], 
            entrada_usuario, 
            cache_hash,
            MODELO_DECISAO,
            timeout=8,
            max_tokens=200
        )
        
        # Fallback heurística se PHI3 falhar
        if decisao.get("erro") or not decisao.get("tool_name"):
            print("🎯 PHI3 falhou - usando heurística")
            decisao = decidir_por_heuristica(entrada_usuario)
        
        # Validação
        schema = carregar_schema(regra["schema"])
        if not validar_json_contra_schema(decisao, schema):
            decisao = decidir_por_heuristica(entrada_usuario)
        
        # 2. FASE EXECUÇÃO API
        print("📡 Fase 2: Executando API...")
        tool_name = decisao.get("tool_name")
        
        if tool_name == "api_call":
            return executar_api_call_hibrido(decisao.get("parameters", {}), mensagem["sessao_id"])
            
        elif tool_name == "api_call_with_presentation":
            # Executa API
            json_resultado = executar_api_call_hibrido(decisao.get("parameters", {}), mensagem["sessao_id"])
            
            # 3. FASE APRESENTAÇÃO: Qwen2 seletivo
            return aplicar_apresentacao_hibrida(
                json_resultado, 
                mensagem["texto"], 
                decisao.get("parameters", {}),
                mensagem["sessao_id"]
            )
                
        else:
            return {"erro": f"Ferramenta não reconhecida: {tool_name}"}
            
    except Exception as e:
        return {"erro": f"Erro no processamento híbrido: {str(e)}"}

def aplicar_apresentacao_hibrida(json_resultado: dict, mensagem_original: str, 
                               params_api: dict, sessao_id: str) -> dict:
    """
    Apresentação híbrida inteligente:
    - Casos simples: Template rápido
    - Casos complexos: Qwen2:7b rica
    """
    
    endpoint = params_api.get("endpoint", "")
    
    # Análise de complexidade para decidir abordagem
    complexidade = analisar_complexidade_resposta(json_resultado, mensagem_original)
    
    print(f"🧠 Complexidade detectada: {complexidade}")
    
    if complexidade == "simples":
        print("⚡ Usando template rápido para caso simples...")
        return aplicar_template_rapido(json_resultado, mensagem_original, endpoint)
    
    elif complexidade == "complexa":
        print("🎨 Usando Qwen2:7b para apresentação rica...")
        return aplicar_llm_apresentacao_rica(json_resultado, mensagem_original, endpoint, sessao_id)
    
    else:  # média
        print("🔀 Tentando LLM rico com fallback para template...")
        try:
            return aplicar_llm_apresentacao_rica(json_resultado, mensagem_original, endpoint, sessao_id, timeout_reduzido=True)
        except:
            print("🔄 LLM falhou, usando template...")
            return aplicar_template_rapido(json_resultado, mensagem_original, endpoint)

def analisar_complexidade_resposta(json_resultado: dict, mensagem_original: str) -> str:
    """
    Analisa complexidade para decidir se usa LLM ou template
    """
    
    # Casos simples (template)
    if "status" in json_resultado and json_resultado.get("status") == "item adicionado":
        return "simples"
    
    if "itens" in json_resultado:
        itens = json_resultado.get("itens", [])
        if len(itens) == 0:  # Carrinho vazio
            return "simples"
        elif len(itens) <= 3:  # Carrinho pequeno
            return "media"
        else:  # Carrinho grande
            return "complexa"
    
    if "resultados" in json_resultado:
        resultados = json_resultado.get("resultados", [])
        total_itens = sum(len(r.get("itens", [])) for r in resultados)
        
        if len(resultados) <= 2 and total_itens <= 4:
            return "media"  # Poucas opções
        elif len(resultados) >= 5 or total_itens >= 10:
            return "complexa"  # Muitas opções, precisa de contexto rico
        else:
            return "media"
    
    # Mensagens complexas
    palavras_complexas = ["qual", "diferenca", "melhor", "comparar", "recomendar", "sugerir"]
    if any(palavra in mensagem_original.lower() for palavra in palavras_complexas):
        return "complexa"
    
    return "media"

def aplicar_template_rapido(json_resultado: dict, mensagem_original: str, endpoint: str) -> dict:
    """Template rápido para casos simples (reutiliza código anterior)"""
    from app.servicos.apresentacao_rica import aplicar_apresentacao_rica
    resultado = aplicar_apresentacao_rica(json_resultado, mensagem_original, endpoint)
    resultado["usou_llm_apresentacao"] = False
    return resultado

def aplicar_llm_apresentacao_rica(json_resultado: dict, mensagem_original: str, 
                                endpoint: str, sessao_id: str, timeout_reduzido: bool = False) -> dict:
    """
    Usa Qwen2:7b para apresentação verdadeiramente rica e contextual
    """
    
    try:
        # Determina prompt de apresentação
        prompt_apresentador = determinar_prompt_apresentador(endpoint, json_resultado)
        
        if not prompt_apresentador:
            return aplicar_template_rapido(json_resultado, mensagem_original, endpoint)
        
        # Busca prompt do apresentador
        prompt_data = get_prompt_cached_super(prompt_apresentador, "autonomo", "1")
        
        if not prompt_data:
            return aplicar_template_rapido(json_resultado, mensagem_original, endpoint)
        
        # Monta contexto rico para o LLM
        contexto_apresentacao = montar_contexto_apresentacao_rico(
            mensagem_original, json_resultado, endpoint
        )
        
        # Cache para apresentação
        cache_hash = hash_prompt(
            prompt_data["template"], 
            contexto_apresentacao, 
            len(prompt_data["exemplos"])
        )
        
        # QWEN2:7b com exemplos completos para apresentação rica
        timeout = 6 if timeout_reduzido else 15
        
        resposta_conversacional = completar_com_modelo_especifico(
            prompt_data["template_otimizado"],
            contexto_apresentacao,
            cache_hash,
            MODELO_APRESENTACAO,
            timeout=timeout,
            max_tokens=800,  # Mais tokens para apresentação rica
            exemplos_completos=True  # Usa todos os exemplos
        )
        
        if "erro" in resposta_conversacional:
            print("⚠️ LLM apresentação falhou, usando template...")
            return aplicar_template_rapido(json_resultado, mensagem_original, endpoint)
        
        # Salva contexto em background
        if sessao_id and sessao_id != "anon":
            contexto_estruturado = resposta_conversacional.get("contexto_estruturado", {})
            if contexto_estruturado and contexto_estruturado.get("produtos"):
                salvar_contexto_background_hibrido(
                    sessao_id, contexto_estruturado, mensagem_original,
                    resposta_conversacional.get("mensagem", "")
                )
        
        resultado_final = {
            "mensagem": resposta_conversacional.get("mensagem", "Resposta processada com sucesso!"),
            "tipo": resposta_conversacional.get("tipo", "apresentacao_rica_llm"),
            "dados_originais": json_resultado,
            "usou_llm_apresentacao": True
        }
        
        # Inclui contexto estruturado se presente
        if resposta_conversacional.get("contexto_estruturado"):
            resultado_final["contexto_estruturado"] = resposta_conversacional["contexto_estruturado"]
        
        return resultado_final
        
    except Exception as e:
        print(f"Erro na apresentação LLM: {e}")
        return aplicar_template_rapido(json_resultado, mensagem_original, endpoint)

def completar_com_modelo_especifico(template_compilado: str, entrada_usuario: str, cache_hash: str,
                                  modelo: str, timeout: int = 10, max_tokens: int = 300, 
                                  exemplos_completos: bool = False) -> dict:
    """
    Completa com modelo específico e configurações otimizadas
    """
    
    # Verifica cache
    if cache_hash in CACHE_RESPOSTAS_LLM:
        entry = CACHE_RESPOSTAS_LLM[cache_hash]
        if time.time() - entry["timestamp"] < CACHE_TTL:
            print(f"⚡ Cache HIT - {modelo}")
            return entry["resposta"]
    
    prompt_final = template_compilado.replace("{ENTRADA_USUARIO}", entrada_usuario)
    
    print(f"🤖 Chamando {modelo} (timeout: {timeout}s, tokens: {max_tokens})...")
    
    try:
        with httpx.Client(timeout=timeout) as client:
            # Configurações específicas por modelo
            if modelo == "phi3:mini":
                options = {
                    "temperature": 0.05,  # Muito baixo para decisões consistentes
                    "top_p": 0.9,
                    "num_predict": max_tokens,
                    "stop": ["\n\n", "```"]
                }
            else:  # qwen2:7b para apresentação
                options = {
                    "temperature": 0.2,   # Mais criatividade para apresentação
                    "top_p": 0.95,
                    "num_predict": max_tokens,
                    "stop": ["```"]
                }
            
            response = client.post(
                f"{config.OLLAMA_HOST}/api/generate",
                json={
                    "model": modelo,
                    "prompt": prompt_final,
                    "format": "json",
                    "stream": False,
                    "options": options
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
                    json_match = re.search(r'\{.*\}', conteudo, re.DOTALL)
                    if json_match:
                        try:
                            return json.loads(json_match.group())
                        except:
                            pass
                    
                    return {"erro": f"{modelo}_json_invalido", "conteudo": conteudo[:200]}
    
    except (httpx.TimeoutException, Exception) as e:
        return {"erro": f"{modelo}_failed", "detalhes": str(e)}

# Funções auxiliares reutilizadas
def executar_api_call_hibrido(params: dict, sessao_id: str) -> dict:
    """Reutiliza execução de API"""
    from app.servicos.executor_fallback_inteligente import executar_api_call_rapido
    return executar_api_call_rapido(params, sessao_id)

def determinar_prompt_apresentador(endpoint: str, json_resultado: dict) -> Optional[str]:
    """Reutiliza determinação de prompt"""
    if "erro" in json_resultado:
        return "prompt_apresentador_erro"
    if "/produtos/busca" in endpoint:
        return "prompt_apresentador_busca"
    if "/carrinhos/" in endpoint:
        return "prompt_apresentador_carrinho"
    return None

def montar_contexto_apresentacao_rico(mensagem_original: str, json_resultado: dict, endpoint: str) -> str:
    """Contexto mais rico para o LLM apresentador"""
    from app.servicos.executor_super_rapido import montar_contexto_apresentacao
    return montar_contexto_apresentacao(mensagem_original, json_resultado, endpoint)

def salvar_contexto_background_hibrido(sessao_id: str, contexto_estruturado: dict, 
                                     mensagem_original: str, resposta_apresentada: str):
    """Salva contexto em background"""
    try:
        payload = {
            "tipo_contexto": "busca_hibrida_rica",
            "contexto_estruturado": contexto_estruturado,
            "mensagem_original": mensagem_original,
            "resposta_apresentada": resposta_apresentada
        }
        httpx.post(f"{API_NEGOCIO_URL}/contexto/{sessao_id}", json=payload, timeout=3.0)
    except:
        pass

def get_stats_hibrido() -> dict:
    """Stats do sistema híbrido"""
    return {
        "cache_prompts": len(CACHE_PROMPTS),
        "cache_llm_responses": len(CACHE_RESPOSTAS_LLM),
        "version": "hibrido_inteligente_v1",
        "modelo_decisao": MODELO_DECISAO,
        "modelo_apresentacao": MODELO_APRESENTACAO,
        "estrategia": "adaptativa_por_complexidade",
        "performance_target": "0.1s decisões + 3s apresentação rica quando necessário"
    }